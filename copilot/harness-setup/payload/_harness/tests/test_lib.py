import unittest

from _harness.tests import helpers  # noqa: F401  (sys.path 設定)
import lib


class FrontmatterTest(unittest.TestCase):
    def test_roundtrip_special_chars(self):
        meta = {"id": "T-20261124-01", "title": '修正: "#1" [bug]', "sessions": ["a", "b"],
                "closed": "", "path": "C:\\tmp"}
        text = lib.dump_frontmatter(meta, "本文\n")
        got, body = lib.parse_frontmatter(text)
        self.assertEqual(got, meta)
        self.assertEqual(list(got), list(meta))
        self.assertEqual(body, "本文\n")

    def test_empty_list(self):
        got, _ = lib.parse_frontmatter(lib.dump_frontmatter({"sessions": []}, ""))
        self.assertEqual(got["sessions"], [])

    def test_no_frontmatter(self):
        self.assertEqual(lib.parse_frontmatter("# title\n"), ({}, "# title\n"))

    def test_bad_frontmatter_raises(self):
        with self.assertRaises(lib.FrontmatterError):
            lib.parse_frontmatter("---\nid: x\n")
        with self.assertRaises(lib.FrontmatterError):
            lib.parse_frontmatter("---\nno colon line\n---\n")


class StateTest(unittest.TestCase):
    def setUp(self):
        self.root = helpers.make_root()

    def test_harness_root_from_env(self):
        self.assertEqual(lib.harness_root(), self.root)

    def test_active_roundtrip(self):
        self.assertIsNone(lib.get_active("s1"))
        lib.set_active("s1", "T-20261124-01")
        self.assertEqual(lib.get_active("s1"), "T-20261124-01")
        lib.clear_active("s1")
        self.assertIsNone(lib.get_active("s1"))

    def test_resolve_task_errors(self):
        with self.assertRaises(lib.HarnessError):
            lib.resolve_task(None, None)
        with self.assertRaises(lib.HarnessError):
            lib.resolve_task(None, "no-active")

    def test_resolve_session_env(self):
        import os
        os.environ["HARNESS_SESSION_ID"] = "env-s"
        try:
            self.assertEqual(lib.resolve_session(None), "env-s")
            self.assertEqual(lib.resolve_session("arg"), "arg")
        finally:
            del os.environ["HARNESS_SESSION_ID"]

    def _make_task(self, tid="T-20261124-01"):
        d = self.root / "_harness/journal/tasks/2026" / tid
        d.mkdir(parents=True)
        (d / "TASK.md").write_text(lib.dump_frontmatter(
            {"id": tid, "title": "t", "type": "bugfix", "repo": "demo", "status": "in_progress",
             "started": "2026-11-24", "touched": "x", "sessions": []}, "\n# t\n"), encoding="utf-8")
        (d / "log.md").write_text(f"# {tid} log\n", encoding="utf-8")
        return tid

    def test_task_lookup_and_update(self):
        tid = self._make_task()
        self.assertEqual(lib.task_dir(tid).name, tid)
        meta = lib.update_task(tid, status="done")
        self.assertEqual(lib.read_task(tid)[0]["status"], "done")
        self.assertNotEqual(meta["touched"], "x")
        with self.assertRaises(lib.HarnessError):
            lib.task_dir("T-19990101-01")

    def test_all_tasks_skips_broken(self):
        self._make_task()
        bad = self.root / "_harness/journal/tasks/2026/T-20261124-02"
        bad.mkdir()
        (bad / "TASK.md").write_text("---\nbroken\n", encoding="utf-8")
        ids = [t["id"] for t in lib.all_tasks()]
        self.assertEqual(ids, ["T-20261124-01"])

    def test_append_log_format(self):
        tid = self._make_task()
        lib.append_log(tid, "verify (exit 0)", "ok")
        text = (lib.task_dir(tid) / "log.md").read_text(encoding="utf-8")
        self.assertIn("\n## 2", text)
        self.assertIn("verify (exit 0)\n\nok\n", text)

    def test_project_meta(self):
        self.assertEqual(lib.project_meta("demo")["verify"], "true")
        with self.assertRaises(lib.HarnessError):
            lib.project_meta("nope")


if __name__ == "__main__":
    unittest.main()

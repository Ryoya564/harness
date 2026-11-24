import re
import unittest

from _harness.tests import helpers
import build_index
import lib
import new_task
import set_task


class TaskScriptsTest(unittest.TestCase):
    def setUp(self):
        self.root = helpers.make_root()

    def test_new_task_creates_files(self):
        tid = new_task.create("期限なしで落ちる: #1", "bugfix", "demo", issue="#1", session="s1")
        self.assertRegex(tid, r"^T-\d{8}-01$")
        d = lib.task_dir(tid)
        for name in ("TASK.md", "log.md", "DECISIONS.md"):
            self.assertTrue((d / name).exists(), name)
        meta, _ = lib.read_task(tid)
        self.assertEqual(list(meta)[:6], ["id", "title", "type", "repo", "issue", "status"])
        self.assertEqual(meta["title"], "期限なしで落ちる: #1")
        self.assertEqual(meta["status"], "in_progress")
        self.assertEqual(meta["verify"], "none")
        self.assertEqual(meta["sessions"], ["s1"])
        self.assertEqual(lib.get_active("s1"), tid)
        self.assertIn(tid, (self.root / "_harness/journal/INDEX.md").read_text(encoding="utf-8"))
        self.assertIn("| 決定 | 理由 | 却下した案 |", (d / "DECISIONS.md").read_text(encoding="utf-8"))

    def test_new_task_without_session(self):
        tid = new_task.create("x", "chore", "demo")
        self.assertEqual(lib.read_task(tid)[0]["sessions"], [])

    def test_new_task_sequence(self):
        a = new_task.create("a", "feature", "demo")
        b = new_task.create("b", "feature", "demo")
        self.assertTrue(a.endswith("-01") and b.endswith("-02"))

    def test_new_task_unknown_repo_exit2(self):
        with self.assertRaises(SystemExit) as cm:
            lib.run_cli(lambda: new_task.main(["--title", "x", "--type", "bugfix",
                                               "--repo", "nope"]))
        self.assertEqual(cm.exception.code, 2)

    def test_new_task_bad_type_exit2(self):
        with self.assertRaises(SystemExit) as cm:
            new_task.main(["--title", "x", "--type", "bogus", "--repo", "demo"])
        self.assertEqual(cm.exception.code, 2)

    def test_set_task_adds_session(self):
        tid = new_task.create("a", "feature", "demo", session="s1")
        lib.update_task(tid, status="open")
        set_task.assign(tid, "s2")
        set_task.assign(tid, "s2")
        meta, _ = lib.read_task(tid)
        self.assertEqual(meta["sessions"], ["s1", "s2"])
        self.assertEqual(meta["status"], "in_progress")
        self.assertEqual(lib.get_active("s2"), tid)

    def test_unknown_task_exit2(self):
        with self.assertRaises(SystemExit) as cm:
            lib.run_cli(lambda: set_task.main(["T-19990101-01", "--session", "s1"]))
        self.assertEqual(cm.exception.code, 2)

    def test_index_sections(self):
        a = new_task.create("open one", "feature", "demo")
        b = new_task.create("closed one", "feature", "demo")
        lib.update_task(b, status="done")
        text = build_index.write_index().read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# タスク索引（自動生成・手で編集しない）"))
        open_part, closed_part = text.split("## 完了・中止")
        self.assertIn(a, open_part)
        self.assertNotIn(b, open_part)
        self.assertIn(b, closed_part)
        self.assertIn("| ID | タイトル | repo | status | touched |", closed_part)

    def test_index_escapes_pipe(self):
        new_task.create("a | b", "feature", "demo")
        text = build_index.write_index().read_text(encoding="utf-8")
        self.assertIn(r"a \| b", text)


if __name__ == "__main__":
    unittest.main()

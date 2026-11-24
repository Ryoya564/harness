import json
import os
import time
import unittest

from _harness.tests import helpers
import doctor
import lib
import new_task


class DoctorTest(unittest.TestCase):
    def setUp(self):
        self.root = helpers.make_root()
        doctor.build_healthy_fixture(self.root)
        self.h = self.root / "_harness"

    def found(self, level, word):
        fs = doctor.run_checks(self.root)
        return [f for f in fs if f.level == level and word in f.what]

    def test_healthy_root_has_no_ng(self):
        new_task.create("x", "chore", "demo", session="s1")
        fs = doctor.run_checks(self.root)
        self.assertEqual([f for f in fs if f.level in ("NG", "WARN")], [])
        self.assertTrue(any(f.level == "INFO" for f in fs))

    def test_ng_hook_missing(self):
        s = json.loads((self.root / ".claude/settings.json").read_text())
        del s["hooks"]["Stop"]
        (self.root / ".claude/settings.json").write_text(json.dumps(s))
        self.assertTrue(self.found("NG", "Stop"))

    def test_ng_hook_script_missing(self):
        (self.h / "hooks/session_end.py").unlink()
        self.assertTrue(self.found("NG", "SessionEnd"))

    def test_ng_settings_missing(self):
        (self.root / ".claude/settings.json").unlink()
        self.assertTrue(self.found("NG", "settings.json"))

    def test_ng_task_frontmatter(self):
        tid = new_task.create("x", "chore", "demo")
        p = lib.task_dir(tid) / "TASK.md"
        p.write_text(p.read_text().replace("type: chore\n", ""))
        self.assertTrue(self.found("NG", "必須キー"))
        p.write_text("---\nbroken\n")
        self.assertTrue(self.found("NG", "frontmatter"))

    def test_ng_control_chars(self):
        tid = new_task.create("x", "chore", "demo")
        with open(lib.task_dir(tid) / "log.md", "a") as f:
            f.write("bad \x07 bell\n")
        self.assertTrue(self.found("NG", "制御文字"))

    def test_tab_is_not_control_char(self):
        with open(self.h / "context/PROFILE.md", "a") as f:
            f.write("\tインデント\n")
        self.assertFalse(self.found("NG", "制御文字"))

    def test_ng_always_read_over_limit(self):
        (self.h / "context/PROFILE.md").write_text("あ" * 3001)
        self.assertTrue(self.found("NG", "上限"))

    def test_ng_project_verify_missing(self):
        (self.h / "context/projects/demo.md").write_text("---\nrepo: demo\n---\n")
        self.assertTrue(self.found("NG", "verify"))

    def test_ng_project_repo_missing(self):
        (self.h / "context/projects/ghost.md").write_text("---\nrepo: ghost\nverify: true\n---\n")
        self.assertTrue(self.found("NG", "repo"))

    def test_ng_done_without_pass(self):
        tid = new_task.create("x", "chore", "demo")
        lib.update_task(tid, status="done")
        self.assertTrue(self.found("NG", "verify"))

    def test_warn_stale_in_progress(self):
        tid = new_task.create("x", "chore", "demo")
        meta, body = lib.read_task(tid)
        meta["touched"] = "2026-01-01T00:00:00+09:00"
        (lib.task_dir(tid) / "TASK.md").write_text(lib.dump_frontmatter(meta, body))
        import build_index
        build_index.write_index()
        self.assertTrue(self.found("WARN", "7日"))

    def test_warn_on_demand_over_limit(self):
        (self.h / "context/knowledge/trap.md").write_text("x" * 3001)
        self.assertTrue(self.found("WARN", "上限"))

    def test_warn_index_stale(self):
        new_task.create("x", "chore", "demo")
        (self.h / "journal/INDEX.md").write_text("# old\n")
        self.assertTrue(self.found("WARN", "INDEX"))

    def test_warn_untasked_session(self):
        (self.h / "journal/sessions.jsonl").write_text(
            json.dumps({"session_id": "orphan", "task_id": None}) + "\n")
        self.assertTrue(self.found("WARN", "セッション"))

    def test_warn_skill_description_long(self):
        d = self.root / ".claude/skills/long"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text("---\nname: long\ndescription: " + "a" * 1025 + "\n---\n")
        self.assertTrue(self.found("WARN", "description"))

    def test_warn_new_hook_errors(self):
        doctor.mark_run(time.time() - 100)
        (self.h / "state/hook-errors.log").write_text(f"{lib.now_iso()} stop_check Boom\n")
        self.assertTrue(self.found("WARN", "hook"))

    def test_old_hook_errors_ignored(self):
        (self.h / "state/hook-errors.log").write_text("2026-01-01T00:00:00+09:00 x Boom\n")
        doctor.mark_run(time.time())
        self.assertFalse(self.found("WARN", "hook"))

    def test_format_report(self):
        fs = [doctor.Finding("NG", "a", "b", "c"), doctor.Finding("INFO", "d", "e", "f")]
        text = doctor.format_report(fs)
        self.assertIn("NG  a  b  c", text)
        self.assertTrue(text.rstrip().endswith("NG 1 / WARN 0 / INFO 1"))

    def test_cli_exit_codes(self):
        self.assertEqual(doctor.main([]), 0)
        self.assertTrue((self.h / "state/doctor-last-run").exists())
        (self.h / "context/PROFILE.md").write_text("あ" * 3001)
        self.assertEqual(doctor.main(["--quiet"]), 1)

    def test_selftest_true(self):
        self.assertTrue(doctor.selftest())
        self.assertEqual(os.environ["HARNESS_ROOT"], str(self.root))


if __name__ == "__main__":
    unittest.main()

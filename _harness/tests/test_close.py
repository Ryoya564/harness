import subprocess
import unittest

from _harness.tests import helpers
import close_task
import lib
import new_task
import verify


class VerifyCloseTest(unittest.TestCase):
    def setUp(self):
        self.root = helpers.make_root()
        self.repo = self.root / "repos/demo"
        self.tid = new_task.create("期限: 修正", "bugfix", "demo", session="s1")

    def log(self) -> str:
        return (lib.task_dir(self.tid) / "log.md").read_text(encoding="utf-8")

    def test_verify_pass_updates_task(self):
        self.assertEqual(verify.run(self.tid), 0)
        self.assertEqual(lib.read_task(self.tid)[0]["verify"], "pass")
        self.assertIn("verify (exit 0)", self.log())

    def test_verify_fail_updates_task(self):
        helpers.set_verify(self.root, "false")
        self.assertEqual(verify.run(self.tid), 1)
        self.assertEqual(lib.read_task(self.tid)[0]["verify"], "fail")
        self.assertIn("verify (exit 1)", self.log())

    def test_verify_tail_and_binary(self):
        helpers.set_verify(
            self.root,
            "python3 -c \"import sys;[print(i) for i in range(100)];"
            "sys.stdout.flush();sys.stdout.buffer.write(bytes([255,10]))\"")
        self.assertEqual(verify.run(self.tid), 0)
        log = self.log()
        self.assertIn("\n99\n", log)
        self.assertNotIn("\n0\n", log)
        self.assertNotIn("\n60\n", log)
        self.assertIn("\n61\n", log)
        self.assertIn("\ufffd", log)

    def test_verify_missing_command_exit2(self):
        (self.root / "_harness/context/projects/demo.md").write_text(
            "---\nrepo: demo\n---\n", encoding="utf-8")
        with self.assertRaises(SystemExit) as cm:
            lib.run_cli(lambda: verify.main([self.tid]))
        self.assertEqual(cm.exception.code, 2)

    def test_close_fails_when_verify_fails(self):
        helpers.set_verify(self.root, "false")
        self.assertEqual(close_task.close(self.tid), 1)
        meta, _ = lib.read_task(self.tid)
        self.assertEqual(meta["status"], "in_progress")
        self.assertEqual(lib.get_active("s1"), self.tid)

    def test_close_commits_repo(self):
        (self.repo / "fix.txt").write_text("fixed\n", encoding="utf-8")
        self.assertEqual(close_task.close(self.tid), 0)
        subj = helpers.git(self.repo, "log", "-1", "--format=%s").strip()
        self.assertEqual(subj, f"{self.tid}: 期限: 修正")
        meta, _ = lib.read_task(self.tid)
        self.assertEqual(meta["status"], "done")
        self.assertRegex(meta["closed"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertIsNone(lib.get_active("s1"))
        self.assertIn("## 完了・中止", (self.root / "_harness/journal/INDEX.md").read_text(
            encoding="utf-8").split(self.tid)[0])

    def test_close_nothing_to_commit(self):
        self.assertEqual(close_task.close(self.tid), 0)
        self.assertEqual(lib.read_task(self.tid)[0]["status"], "done")
        self.assertEqual(helpers.git(self.repo, "rev-list", "--count", "HEAD").strip(), "1")

    def test_close_commits_harness_journal(self):
        helpers.git(self.root, "init", "-q", "-b", "main")
        (self.root / "other.txt").write_text("untouched\n", encoding="utf-8")
        self.assertEqual(close_task.close(self.tid), 0)
        subj = helpers.git(self.root, "log", "-1", "--format=%s").strip()
        self.assertEqual(subj, f"journal: {self.tid} close")
        files = helpers.git(self.root, "show", "--name-only", "--format=", "HEAD")
        self.assertIn("_harness/journal/", files)
        self.assertNotIn("other.txt", files)

    def test_drop(self):
        self.assertEqual(close_task.close(self.tid, drop_reason="不要"), 0)
        self.assertEqual(lib.read_task(self.tid)[0]["status"], "dropped")
        self.assertIn("不要", self.log())
        self.assertNotIn("verify (exit", self.log())

    def test_cli_uses_active_session(self):
        out = subprocess.run(
            ["python3", str(helpers.SCRIPTS / "close_task.py"), "--session", "s1"],
            capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(lib.read_task(self.tid)[0]["status"], "done")


if __name__ == "__main__":
    unittest.main()

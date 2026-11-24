import json
import os
import subprocess
import time
import unittest

from _harness.tests import helpers
import lib
import new_task
import stop_check


class StopHookTest(unittest.TestCase):
    def setUp(self):
        self.root = helpers.make_root()
        self.repo = self.root / "repos/demo"
        self.now = time.time()

    def payload(self, sid="s1", active=False):
        # Copilot の agentStop と同じ camelCase の形
        return {"sessionId": sid, "transcriptPath": f"/t/{sid}.json", "stopReason": "end_turn",
                "stop_hook_active": active}

    def touch_repo(self, name="a.py", mtime=None):
        f = self.repo / name
        f.write_text(f"x = {time.time()}\n", encoding="utf-8")
        t = mtime if mtime is not None else self.now
        os.utime(f, (t, t))
        return f

    def task(self, sid="s1", log_age=3600):
        tid = new_task.create("demo", "bugfix", "demo", session=sid)
        log = lib.task_dir(tid) / "log.md"
        os.utime(log, (self.now - log_age, self.now - log_age))
        return tid

    def test_active_flag_passes(self):
        self.touch_repo()
        self.assertIsNone(stop_check.evaluate(self.payload(active=True), self.now))

    def test_camel_case_active_flag_passes(self):
        self.touch_repo()
        p = self.payload()
        del p["stop_hook_active"]
        p["stopHookActive"] = True
        self.assertIsNone(stop_check.evaluate(p, self.now))

    def test_clean_passes(self):
        self.assertIsNone(stop_check.evaluate(self.payload(), self.now))

    def test_a_untasked_edit_blocks(self):
        self.touch_repo("README.md")
        res = stop_check.evaluate(self.payload(), self.now)
        self.assertEqual(res["decision"], "block")
        self.assertTrue(res["reason"].startswith("記録漏れがあります。"))
        self.assertIn("タスクが割り当てられていません", res["reason"])

    def test_a_not_after_task_closed_in_session(self):
        import close_task
        tid = new_task.create("demo", "bugfix", "demo", session="s1")
        self.touch_repo()
        self.assertEqual(close_task.close(tid), 0)
        self.assertIsNone(stop_check.evaluate(self.payload(), self.now))

    def test_a_dirty_after_task_closed_still_blocks(self):
        import close_task
        tid = new_task.create("demo", "bugfix", "demo", session="s1")
        self.assertEqual(close_task.close(tid), 0)
        self.touch_repo("late.py")
        res = stop_check.evaluate(self.payload(), self.now)
        self.assertIn("タスクが割り当てられていません", res["reason"])

    def test_a_ignores_edits_outside_repos(self):
        (self.root / "_harness/context/PROFILE.md").write_text("x\n")
        self.assertIsNone(stop_check.evaluate(self.payload(), self.now))

    def test_a_ignores_dirty_from_before_session(self):
        stop_check.mark_session_start("s9", self.now - 100)
        self.touch_repo(mtime=self.now - 3600)
        self.assertIsNone(stop_check.evaluate(self.payload("s9"), self.now))

    def test_a_dirty_repo_blocks(self):
        stop_check.mark_session_start("s1", self.now - 100)
        self.touch_repo()
        res = stop_check.evaluate(self.payload(), self.now)
        self.assertIn("タスクが割り当てられていません", res["reason"])

    def test_b_blocks_after_30min(self):
        tid = self.task(log_age=3600)
        self.touch_repo(mtime=self.now - 60)
        res = stop_check.evaluate(self.payload(), self.now)
        self.assertIn(f"{tid} の log.md", res["reason"])

    def test_b_not_within_30min(self):
        self.task(log_age=600)
        self.touch_repo(mtime=self.now - 60)
        self.assertIsNone(stop_check.evaluate(self.payload(), self.now))

    def test_b_not_when_log_newer(self):
        self.task(log_age=3600)
        self.touch_repo(mtime=self.now - 7200)
        self.assertIsNone(stop_check.evaluate(self.payload(), self.now))

    def test_c_missing_session_blocks(self):
        tid = new_task.create("demo", "bugfix", "demo")
        lib.set_active("s1", tid)
        res = stop_check.evaluate(self.payload(), self.now)
        self.assertIn(f"set_task.py {tid} --session s1", res["reason"])

    def test_same_fingerprint_blocks_once(self):
        self.task(log_age=3600)
        self.touch_repo(mtime=self.now - 60)
        self.assertIsNotNone(stop_check.evaluate(self.payload(), self.now))
        self.assertIsNone(stop_check.evaluate(self.payload(), self.now))

    def test_new_change_blocks_again(self):
        self.task(log_age=3600)
        self.touch_repo(mtime=self.now - 60)
        self.assertIsNotNone(stop_check.evaluate(self.payload(), self.now))
        self.touch_repo("b.py", mtime=self.now - 30)
        self.assertIsNotNone(stop_check.evaluate(self.payload(), self.now))

    def test_fingerprints_are_per_session(self):
        self.touch_repo()
        self.assertIsNotNone(stop_check.evaluate(self.payload("s1"), self.now))
        self.assertIsNotNone(stop_check.evaluate(self.payload("s2"), self.now))

    def test_bad_stdin_passes(self):
        self.touch_repo()
        out = subprocess.run(["python3", str(helpers.HOOKS / "stop_check.py")], input="{bad",
                             capture_output=True, text=True, cwd="/")
        self.assertEqual(out.returncode, 0)
        self.assertEqual(out.stdout.strip(), "")

    def test_hook_outputs_block_json(self):
        self.touch_repo()
        out = subprocess.run(["python3", str(helpers.HOOKS / "stop_check.py")],
                             input=json.dumps(self.payload()), capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads(out.stdout)["decision"], "block")


if __name__ == "__main__":
    unittest.main()

import json
import os
import subprocess
import time
import unittest

from _harness.tests import helpers
import _common
import lib
import new_task
import session_end
import session_start


def run_hook(name: str, stdin: str, env_extra: dict | None = None):
    env = {**os.environ, **(env_extra or {})}
    return subprocess.run(["python3", str(helpers.HOOKS / f"{name}.py")], input=stdin,
                          capture_output=True, text=True, env=env, cwd="/")


class SessionStartTest(unittest.TestCase):
    def setUp(self):
        self.root = helpers.make_root()

    def test_start_lists_open_tasks_and_issues(self):
        tid = new_task.create("demo bug を直す", "bugfix", "demo", issue="#1")
        lib.append_log(tid, "作業", "次にやること: テストを足す")
        ctx = session_start.build_context({"session_id": "s9"}, time.time())
        self.assertIn("## セッション", ctx)
        self.assertIn("--session s9", ctx)
        self.assertIn(f"- {tid} demo bug を直す（demo）次: テストを足す", ctx)
        issues = ctx.split("## 未着手の Issue")[1]
        self.assertIn("#2 [feature] demo feat", issues)
        self.assertNotIn("#1 [bug]", issues)

    def test_start_no_next_step(self):
        tid = new_task.create("x", "chore", "demo")
        ctx = session_start.build_context({"session_id": "s9"}, time.time())
        self.assertIn(f"- {tid} x（demo）次: 記録なし", ctx)

    def test_start_hook_output_and_env_file(self):
        env_file = self.root / "env.sh"
        out = run_hook("session_start", json.dumps({"session_id": "abc"}),
                       {"CLAUDE_ENV_FILE": str(env_file)})
        self.assertEqual(out.returncode, 0, out.stderr)
        data = json.loads(out.stdout)
        self.assertEqual(data["hookSpecificOutput"]["hookEventName"], "SessionStart")
        self.assertIn("abc", data["hookSpecificOutput"]["additionalContext"])
        self.assertEqual(env_file.read_text(), "export HARNESS_SESSION_ID=abc\n")

    def test_start_runs_doctor_weekly(self):
        ctx = session_start.build_context({"session_id": "s9"}, time.time())
        self.assertIn("## doctor", ctx)
        self.assertIn("NG", ctx.split("## doctor")[1])
        self.assertTrue((self.root / "_harness/state/doctor-last-run").exists())
        ctx2 = session_start.build_context({"session_id": "s9"}, time.time())
        self.assertNotIn("## doctor", ctx2)

    def test_bad_stdin_passes(self):
        out = run_hook("session_start", "{bad")
        self.assertEqual(out.returncode, 0)
        self.assertIn("SessionStart", out.stdout)
        self.assertFalse((self.root / "_harness/state/hook-errors.log").exists())

    def test_exception_logged(self):
        def boom():
            raise RuntimeError("故障テスト")
        with self.assertRaises(SystemExit) as cm:
            _common.safe_main("session_start", boom)
        self.assertEqual(cm.exception.code, 0)
        log = (self.root / "_harness/state/hook-errors.log").read_text(encoding="utf-8")
        self.assertIn("session_start", log)
        self.assertIn("故障テスト", log)


class SessionEndTest(unittest.TestCase):
    def setUp(self):
        self.root = helpers.make_root()
        self.jsonl = self.root / "_harness/journal/sessions.jsonl"

    def test_end_dedups_sessions(self):
        session_end.record({"session_id": "s1", "transcript_path": "/a", "reason": "exit"})
        session_end.record({"session_id": "s2", "transcript_path": "/b", "reason": "exit"})
        session_end.record({"session_id": "s1", "transcript_path": "/a2", "reason": "clear"})
        rows = [json.loads(x) for x in self.jsonl.read_text().splitlines()]
        self.assertEqual([r["session_id"] for r in rows], ["s2", "s1"])
        self.assertEqual(rows[1]["transcript_path"], "/a2")

    def test_end_records_task_and_touch(self):
        tid = new_task.create("x", "chore", "demo", session="s1")
        lib.update_task(tid, touched="old")
        session_end.record({"session_id": "s1", "transcript_path": "/a", "reason": "exit"})
        row = json.loads(self.jsonl.read_text().splitlines()[0])
        self.assertEqual(row["task_id"], tid)
        self.assertNotEqual(lib.read_task(tid)[0]["touched"], "old")
        self.assertEqual(lib.get_active("s1"), tid)

    def test_end_bad_stdin_passes(self):
        out = run_hook("session_end", "")
        self.assertEqual(out.returncode, 0)


if __name__ == "__main__":
    unittest.main()

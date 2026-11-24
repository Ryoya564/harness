import json
import subprocess
import unittest

from _harness.tests import helpers
import guard


def shell(cmd, name="bash", as_string=True):
    args = {"command": cmd}
    return {"toolName": name, "toolArgs": json.dumps(args) if as_string else args}


class GuardTest(unittest.TestCase):
    def setUp(self):
        helpers.make_root()

    def denied(self, payload):
        res = guard.decide(payload)
        return bool(res) and res["permissionDecision"] == "deny"

    def test_denies_git_push(self):
        self.assertTrue(self.denied(shell("git push origin main")))

    def test_denies_git_push_with_dash_c(self):
        self.assertTrue(self.denied(shell("git -C repos/x push")))

    def test_denies_push_after_other_command(self):
        self.assertTrue(self.denied(shell("git add -A && git commit -m x && git push")))

    def test_denies_rm_rf_variants(self):
        for cmd in ("rm -rf build", "rm -fr build", "rm -r -f build", "rm --recursive --force x",
                    "sudo rm -Rf /tmp/x"):
            with self.subTest(cmd=cmd):
                self.assertTrue(self.denied(shell(cmd)))

    def test_denies_when_args_are_object(self):
        self.assertTrue(self.denied(shell("git push", as_string=False)))

    def test_denies_vscode_format_terminal_tool(self):
        payload = {"tool_name": "run_in_terminal", "tool_input": {"command": "git push"}}
        self.assertTrue(self.denied(payload))

    def test_deny_has_reason(self):
        res = guard.decide(shell("git push"))
        self.assertIn("push", res["permissionDecisionReason"])

    def test_allows_safe_commands(self):
        for cmd in ("git status", "git commit -m 'push later'", "rm a.txt", "rm -r build",
                    "python3 _harness/scripts/verify.py T-1", "echo git-pusher"):
            with self.subTest(cmd=cmd):
                self.assertIsNone(guard.decide(shell(cmd)))

    def test_ignores_non_shell_tools(self):
        # ドキュメントに "git push" と書くだけの編集は止めない
        payload = {"toolName": "edit", "toolArgs": {"content": "run git push and rm -rf x"}}
        self.assertIsNone(guard.decide(payload))

    def test_hook_outputs_one_json_object(self):
        out = subprocess.run(["python3", str(helpers.HOOKS / "guard.py")],
                             input=json.dumps(shell("git push")), capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads(out.stdout)["permissionDecision"], "deny")

    def test_hook_allows_with_empty_object(self):
        out = subprocess.run(["python3", str(helpers.HOOKS / "guard.py")],
                             input=json.dumps(shell("ls")), capture_output=True, text=True)
        self.assertEqual(json.loads(out.stdout), {})

    def test_bad_stdin_passes(self):
        out = subprocess.run(["python3", str(helpers.HOOKS / "guard.py")], input="{bad",
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 0)


if __name__ == "__main__":
    unittest.main()

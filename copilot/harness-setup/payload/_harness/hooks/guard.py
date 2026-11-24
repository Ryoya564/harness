"""preToolUse: 人に戻すべき操作（git push・rm -rf）をシェル実行の前に止める。

Copilot には settings の allow/deny がないため、規約 §6 の禁止事項はここで機械的に守る。
シェル以外のツール（ファイル編集など）は対象外。判定できなければ {} を返し、通常の承認に任せる。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common  # noqa: E402

SHELL_HINTS = ("bash", "shell", "powershell", "terminal", "execute", "exec", "command")
GIT_PUSH = re.compile(r"\bgit\b(?:\s+-C\s+\S+|\s+-c\s+\S+|\s+--?[\w-]+(?:=\S+)?)*\s+push\b")
PUSH_REASON = "git push は禁止です（外部への送信はユーザーに戻す: 規約 §6）。push はユーザーが行います"
RM_REASON = ("rm -rf は禁止です（破壊的な操作はユーザーに戻す: 規約 §6）。"
             "削除が必要ならユーザーに選択肢で確認する")
SEGMENT = re.compile(r"&&|\|\||[;|&\n]")
PREFIXES = {"sudo", "command", "env", "nohup", "time"}


def _is_rm_rf(segment: str) -> bool:
    tokens = segment.split()
    while tokens and tokens[0] in PREFIXES:
        tokens.pop(0)
    if not tokens or tokens[0].rsplit("/", 1)[-1] != "rm":
        return False
    short = "".join(t[1:] for t in tokens[1:] if t.startswith("-") and not t.startswith("--"))
    recursive = "r" in short.lower() or "--recursive" in tokens
    force = "f" in short or "--force" in tokens
    return recursive and force


def _command_text(args: object) -> str:
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            return args
    if isinstance(args, dict):
        for key in ("command", "cmd", "commandLine", "script", "input"):
            if isinstance(args.get(key), str):
                return args[key]
        return " ".join(v for v in args.values() if isinstance(v, str))
    if isinstance(args, list):
        return " ".join(str(a) for a in args)
    return ""


def decide(payload: dict) -> dict | None:
    payload = _common.normalize(payload)
    name = str(payload.get("tool_name") or "").lower()
    if not any(h in name for h in SHELL_HINTS):
        return None
    text = _command_text(payload.get("tool_input"))
    reason = None
    if GIT_PUSH.search(text):
        reason = PUSH_REASON
    elif any(_is_rm_rf(s) for s in SEGMENT.split(text)):
        reason = RM_REASON
    if reason:
        return {"permissionDecision": "deny", "permissionDecisionReason": reason}
    return None


def main() -> None:
    res = decide(_common.read_payload())
    print(json.dumps(res or {}, ensure_ascii=False))


if __name__ == "__main__":
    _common.safe_main("guard", main)

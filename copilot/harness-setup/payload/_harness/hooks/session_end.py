"""sessionEnd: 会話原本の所在を sessions.jsonl に残す（同じ session_id は最新で置換）。止めない。

Copilot の sessionEnd は transcriptPath を渡さないので、agentStop が控えた値で補う。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common  # noqa: E402
from _common import lib  # noqa: E402


def record(payload: dict) -> None:
    import stop_check  # noqa: PLC0415
    payload = _common.normalize(payload)
    sid = payload.get("session_id")
    if not sid:
        return
    active = lib.get_active(sid)
    task_id = active
    if not task_id:
        recent = lib.session_tasks(sid)
        task_id = recent[0] if recent else None
    path = lib.journal_dir() / "sessions.jsonl"
    rows = []
    if path.exists():
        for line in lib.read_text(path).splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("session_id") != sid:
                rows.append(row)
    transcript = payload.get("transcript_path") or stop_check.remembered_transcript(sid)
    rows.append({"session_id": sid, "transcript_path": transcript,
                 "ended_at": lib.now_iso(), "reason": payload.get("reason"),
                 "task_id": task_id})
    lib.write_text(path, "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    if active:  # touched を更新するのは作業中のタスクだけ（close 済みは触らない）
        try:
            lib.update_task(active)
            import build_index  # noqa: PLC0415
            build_index.write_index()
        except lib.HarnessError:
            pass


if __name__ == "__main__":
    _common.safe_main("session_end", lambda: record(_common.read_payload()))

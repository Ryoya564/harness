"""既存タスクをこのセッションの現在タスクにする。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_index  # noqa: E402
import lib  # noqa: E402


def assign(task_id: str, session: str | None) -> None:
    meta, _ = lib.read_task(task_id)
    sessions = list(meta.get("sessions") or [])
    if session and session not in sessions:
        sessions.append(session)
    lib.update_task(task_id, sessions=sessions, status="in_progress")
    if session:
        lib.set_active(session, task_id)
    build_index.write_index()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("task_id")
    ap.add_argument("--session")
    a = ap.parse_args(argv)
    session = lib.resolve_session(a.session)
    assign(a.task_id, session)
    print(f"{a.task_id} を現在タスクにしました（session={session or 'なし'}）")
    return 0


if __name__ == "__main__":
    lib.run_cli(main)

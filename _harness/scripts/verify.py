"""タスクの repo で verify コマンドを実行し、結果を記録する。終了コードをそのまま返す。"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402

TAIL_LINES = 40


def _tail(data: bytes) -> str:
    lines = data.decode("utf-8", errors="replace").splitlines()
    return "\n".join(lines[-TAIL_LINES:])


def run(task_id: str) -> int:
    meta, _ = lib.read_task(task_id)
    repo = str(meta.get("repo") or "")
    cmd = str(lib.project_meta(repo).get("verify") or "").strip()
    if not cmd:
        raise lib.HarnessError(f"context/projects/{repo}.md に verify: がありません")
    cwd = lib.repo_dir(repo)
    if not cwd.is_dir():
        raise lib.HarnessError(f"repo がありません: {cwd}")
    proc = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True)
    code = proc.returncode
    body = f"コマンド: `{cmd}`\n\n```\n{_tail(proc.stdout)}\n```"
    if proc.stderr.strip():
        body += f"\n\nstderr:\n\n```\n{_tail(proc.stderr)}\n```"
    lib.append_log(task_id, f"verify (exit {code})", body)
    lib.update_task(task_id, verify="pass" if code == 0 else "fail")
    return code


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("task_id", nargs="?")
    ap.add_argument("--session")
    a = ap.parse_args(argv)
    tid = lib.resolve_task(a.task_id, lib.resolve_session(a.session))
    code = run(tid)
    print(f"{tid}: verify {'pass' if code == 0 else 'fail'} (exit {code})")
    return code


if __name__ == "__main__":
    lib.run_cli(main)

"""タスクを完了（verify 成功時のみ）または中止にし、記録と commit を行う。push はしない。"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_index  # noqa: E402
import lib  # noqa: E402
import verify  # noqa: E402


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True)


def _is_own_repo(path: Path) -> bool:
    out = _git(path, "rev-parse", "--show-toplevel")
    return out.returncode == 0 and Path(out.stdout.strip()).resolve() == path.resolve()


def _commit(cwd: Path, message: str, paths: list[str]) -> str:
    """変更があれば commit してハッシュを返す。なければ空文字。"""
    if not _is_own_repo(cwd):
        return ""
    _git(cwd, "add", "-A", "--", *paths)
    if _git(cwd, "diff", "--cached", "--quiet").returncode == 0:
        return ""
    res = _git(cwd, "commit", "-q", "-m", message)
    if res.returncode != 0:
        raise lib.HarnessError(f"commit に失敗しました ({cwd}): {res.stderr.strip()}")
    return _git(cwd, "rev-parse", "--short", "HEAD").stdout.strip()


def _release_active(task_id: str) -> None:
    active_dir = lib.journal_dir() / "active"
    for p in active_dir.glob("*") if active_dir.is_dir() else []:
        if lib.read_text(p).strip() == task_id:
            p.unlink()


def close(task_id: str, drop_reason: str | None = None) -> int:
    meta, _ = lib.read_task(task_id)
    lines = []
    if drop_reason is None:
        code = verify.run(task_id)
        if code != 0:
            print(f"{task_id}: verify が失敗したため完了にしません (exit {code})")
            return 1
        lib.update_task(task_id, status="done", closed=date.today().isoformat())
        sha = _commit(lib.repo_dir(str(meta["repo"])), f"{task_id}: {meta['title']}", ["."])
        lines.append(f"repo commit: {sha}" if sha else "repo commit: 変更なしのため省略")
        heading = "close (done)"
    else:
        lib.update_task(task_id, status="dropped", closed=date.today().isoformat())
        lines.append(f"中止理由: {drop_reason}")
        heading = "close (dropped)"
    _release_active(task_id)
    lib.append_log(task_id, heading, "\n".join(lines))
    build_index.write_index()
    root = lib.harness_root()
    hsha = _commit(root, f"journal: {task_id} close", ["_harness/journal", "_harness/context"])
    lines.append(f"harness commit: {hsha}" if hsha else "harness commit: 省略（git 外か変更なし）")
    print(f"{task_id}: {heading}\n" + "\n".join(lines))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("task_id", nargs="?")
    ap.add_argument("--session")
    ap.add_argument("--drop", metavar="理由")
    a = ap.parse_args(argv)
    tid = lib.resolve_task(a.task_id, lib.resolve_session(a.session))
    return close(tid, a.drop)


if __name__ == "__main__":
    lib.run_cli(main)

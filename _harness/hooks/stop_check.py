"""Stop: 記録漏れがあれば止める。同じ状態（指紋）で止めるのはセッションごとに1回だけ。"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common  # noqa: E402
from _common import lib  # noqa: E402

LOG_GRACE = 30 * 60
EDIT_TOOLS = {"Edit", "Write", "NotebookEdit", "MultiEdit"}


def edited_repo_paths(transcript_path: str | None) -> set[str]:
    """transcript から repos/ 配下への編集パスを集める。読めなければ空集合。"""
    if not transcript_path:
        return set()
    repos = (lib.harness_root() / "repos").resolve()
    found: set[str] = set()
    try:
        with open(transcript_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    content = json.loads(line).get("message", {}).get("content")
                except (json.JSONDecodeError, AttributeError):
                    continue
                if not isinstance(content, list):
                    continue
                for item in content:
                    if not isinstance(item, dict) or item.get("type") != "tool_use":
                        continue
                    if item.get("name") not in EDIT_TOOLS:
                        continue
                    inp = item.get("input") or {}
                    fp = inp.get("file_path") or inp.get("notebook_path")
                    if fp and Path(fp).resolve().is_relative_to(repos):
                        found.add(str(Path(fp).resolve()))
    except OSError:
        return set()
    return found


def dirty_files(repo: Path) -> list[tuple[str, float]]:
    """git status --porcelain に出るファイルのうち実在するものと mtime。"""
    res = subprocess.run(["git", "-C", str(repo), "status", "--porcelain", "-uall", "-z"],
                         capture_output=True, text=True)
    if res.returncode != 0:
        return []
    out = []
    entries = res.stdout.split("\0")
    i = 0
    while i < len(entries):
        e = entries[i]
        i += 1
        if len(e) < 4:
            continue
        if e[0] in "RC":
            i += 1  # rename/copy は元パスが続く
        p = repo / e[3:]
        if p.is_file():
            out.append((str(p), p.stat().st_mtime))
    return out


def _fingerprint(tag: str, files: list[tuple[str, float]] | set[str]) -> str:
    items = sorted(f"{p}:{m}" for p, m in files) if isinstance(files, list) else sorted(files)
    return hashlib.sha256((tag + "|" + "\n".join(items)).encode()).hexdigest()[:16]


def _load_blocks() -> dict:
    p = lib.state_dir() / "stop-blocks.json"
    try:
        return json.loads(lib.read_text(p)) if p.exists() else {}
    except json.JSONDecodeError:
        return {}


def evaluate(payload: dict, now: float) -> dict | None:
    if payload.get("stop_hook_active"):
        return None
    sid = payload.get("session_id")
    if not sid:
        return None
    task_id = lib.get_active(sid)
    hits: list[tuple[str, str]] = []  # (指紋, 理由の行)

    if not task_id:
        edits = edited_repo_paths(payload.get("transcript_path"))
        dirty = [d for r in sorted((lib.harness_root() / "repos").glob("*/"))
                 for d in dirty_files(r)]
        if edits or dirty:
            hits.append((_fingerprint("a", dirty) + _fingerprint("a", edits),
                         "repos/ を変更していますがタスクが割り当てられていません。"
                         "new_task.py か set_task.py を実行してください"))
    else:
        try:
            meta, _ = lib.read_task(task_id)
        except lib.HarnessError:
            return None
        if sid not in (meta.get("sessions") or []):
            hits.append((f"c|{task_id}",
                         f"set_task.py {task_id} --session {sid} でこのセッションを記録してください"))
        log = lib.task_dir(task_id) / "log.md"
        log_mtime = log.stat().st_mtime if log.exists() else 0.0
        dirty = dirty_files(lib.repo_dir(str(meta.get("repo") or "")))
        if dirty and max(m for _, m in dirty) > log_mtime and now - log_mtime >= LOG_GRACE:
            hits.append((_fingerprint("b", dirty),
                         f"{task_id} の log.md に、作業内容・判断・次にやることを追記してください"
                         "（完了なら close_task.py）"))

    blocks = _load_blocks()
    seen = set(blocks.get(sid, []))
    fresh = [(fp, msg) for fp, msg in hits if fp not in seen]
    if not fresh:
        return None
    blocks[sid] = sorted(seen | {fp for fp, _ in fresh})
    lib.write_text(lib.state_dir() / "stop-blocks.json",
                   json.dumps(blocks, ensure_ascii=False, indent=1))
    reason = "記録漏れがあります。次を済ませてから終了してください:\n" + "\n".join(
        f"- {msg}" for _, msg in fresh)
    return {"decision": "block", "reason": reason}


def main() -> None:
    res = evaluate(_common.read_payload(), time.time())
    if res:
        print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    _common.safe_main("stop_check", main)

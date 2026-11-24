"""タスクを作り、このセッションの現在タスクにする。task_id を出力する。"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_index  # noqa: E402
import lib  # noqa: E402

TYPES = ("feature", "bugfix", "refactor", "chore")


def _next_id(today: date) -> str:
    prefix = f"T-{today:%Y%m%d}-"
    nums = [int(m.group(1)) for p in (lib.journal_dir() / "tasks").glob(f"*/{prefix}*")
            if (m := re.fullmatch(re.escape(prefix) + r"(\d+)", p.name))]
    return f"{prefix}{max(nums, default=0) + 1:02d}"


def _template(name: str, **kw: str) -> str:
    text = lib.read_text(lib.hdir() / "templates" / name)
    for k, v in kw.items():
        text = text.replace("{" + k + "}", v)
    return text


def create(title: str, type_: str, repo: str, issue: str | None = None,
           session: str | None = None) -> str:
    if type_ not in TYPES:
        raise lib.HarnessError(f"type は {', '.join(TYPES)} のいずれか: {type_}")
    if not lib.repo_dir(repo).is_dir():
        raise lib.HarnessError(f"repo がありません: {lib.repo_dir(repo)}")
    today = date.today()
    tid = _next_id(today)
    d = lib.journal_dir() / "tasks" / f"{today:%Y}" / tid
    d.mkdir(parents=True)
    now = lib.now_iso()
    meta = {"id": tid, "title": title, "type": type_, "repo": repo, "issue": issue or "",
            "status": "in_progress", "started": today.isoformat(), "closed": "",
            "touched": now, "sessions": [session] if session else [], "verify": "none"}
    lib.write_text(d / "TASK.md", lib.dump_frontmatter(meta, _template("TASK.md", title=title)))
    lib.write_text(d / "log.md", _template("log.md", id=tid))
    lib.write_text(d / "DECISIONS.md", _template("DECISIONS.md", id=tid))
    (d / "artifacts").mkdir()
    if session:
        lib.set_active(session, tid)
    build_index.write_index()
    return tid


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--title", required=True)
    ap.add_argument("--type", required=True, choices=TYPES)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--issue")
    ap.add_argument("--session")
    a = ap.parse_args(argv)
    print(create(a.title, a.type, a.repo, a.issue, lib.resolve_session(a.session)))
    return 0


if __name__ == "__main__":
    lib.run_cli(main)

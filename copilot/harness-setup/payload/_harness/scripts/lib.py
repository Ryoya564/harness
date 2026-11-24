"""ハーネス共通処理（Python 標準ライブラリのみ）。"""
from __future__ import annotations

import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable, NoReturn

Value = str | list[str]


class HarnessError(Exception):
    """利用者向けのエラー。CLI は exit 2 で終わる。"""


class FrontmatterError(ValueError):
    pass


# ---------------------------------------------------------------- パス・時刻

def harness_root() -> Path:
    env = os.environ.get("HARNESS_ROOT")
    return Path(env) if env else Path(__file__).resolve().parents[2]


def hdir() -> Path:
    return harness_root() / "_harness"


def journal_dir() -> Path:
    return hdir() / "journal"


def state_dir() -> Path:
    d = hdir() / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def now_iso() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


# ---------------------------------------------------------------- frontmatter

_NEEDS_QUOTE = re.compile(r'[:#\[\],"\\]|^\s|\s$')


def _quote(s: str) -> str:
    if s == "" or not _NEEDS_QUOTE.search(s):
        return s
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _parse_scalar(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        out, i, inner = [], 0, s[1:-1]
        while i < len(inner):
            if inner[i] == "\\" and i + 1 < len(inner):
                out.append(inner[i + 1])
                i += 2
            else:
                out.append(inner[i])
                i += 1
        return "".join(out)
    return s


def _split_list(s: str) -> list[str]:
    items, cur, in_q, esc = [], [], False, False
    for ch in s:
        if esc:
            cur.append(ch)
            esc = False
        elif ch == "\\" and in_q:
            cur.append(ch)
            esc = True
        elif ch == '"':
            cur.append(ch)
            in_q = not in_q
        elif ch == "," and not in_q:
            items.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    if "".join(cur).strip() or items:
        items.append("".join(cur))
    return [_parse_scalar(x) for x in items]


def parse_frontmatter(text: str) -> tuple[dict[str, Value], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 3)
    if end == -1:
        if text.endswith("\n---"):
            end = len(text) - 4
        else:
            raise FrontmatterError("frontmatter の閉じ '---' がありません")
    block = text[4:end]
    body = text[end + 5:]
    meta: dict[str, Value] = {}
    for line in block.split("\n"):
        if not line.strip():
            continue
        if ":" not in line:
            raise FrontmatterError(f"key: value 形式ではない行: {line!r}")
        key, _, raw = line.partition(":")
        key, raw = key.strip(), raw.strip()
        if raw.startswith("[") and raw.endswith("]"):
            meta[key] = _split_list(raw[1:-1])
        else:
            meta[key] = _parse_scalar(raw)
    return meta, body


def dump_frontmatter(meta: dict[str, Value], body: str) -> str:
    lines = ["---"]
    for key, val in meta.items():
        if key.startswith("_"):
            continue
        if isinstance(val, list):
            lines.append(f"{key}: [{', '.join(_quote(v) for v in val)}]")
        else:
            lines.append(f"{key}: {_quote(str(val))}".rstrip())
    lines.append("---")
    return "\n".join(lines) + "\n" + body


# ---------------------------------------------------------------- タスク

def task_dir(task_id: str) -> Path:
    for p in sorted((journal_dir() / "tasks").glob(f"*/{task_id}")):
        if (p / "TASK.md").exists():
            return p
    raise HarnessError(f"タスクが見つかりません: {task_id}")


def read_task(task_id: str) -> tuple[dict[str, Value], str]:
    path = task_dir(task_id) / "TASK.md"
    try:
        return parse_frontmatter(read_text(path))
    except FrontmatterError as e:
        raise HarnessError(f"TASK.md を読めません: {path}: {e}") from e


def update_task(task_id: str, **fields: Value) -> dict[str, Value]:
    meta, body = read_task(task_id)
    meta.update(fields)
    meta["touched"] = now_iso()
    write_text(task_dir(task_id) / "TASK.md", dump_frontmatter(meta, body))
    return meta


def all_tasks() -> list[dict]:
    tasks = []
    for path in sorted((journal_dir() / "tasks").glob("*/*/TASK.md")):
        try:
            meta, _ = parse_frontmatter(read_text(path))
        except (FrontmatterError, UnicodeDecodeError):
            continue
        if not meta.get("id"):
            continue
        meta["_path"] = path
        tasks.append(meta)
    return tasks


def append_log(task_id: str, heading: str, body: str) -> None:
    path = task_dir(task_id) / "log.md"
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(f"\n## {now_iso()} {heading}\n\n{body.rstrip()}\n")


# ---------------------------------------------------------------- セッション

def resolve_session(arg: str | None) -> str | None:
    return arg or os.environ.get("HARNESS_SESSION_ID") or None


def _active_path(session_id: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9._-]+", session_id):
        raise HarnessError(f"不正なセッションID: {session_id!r}")
    return journal_dir() / "active" / session_id


def get_active(session_id: str | None) -> str | None:
    if not session_id:
        return None
    p = _active_path(session_id)
    return read_text(p).strip() or None if p.exists() else None


def set_active(session_id: str, task_id: str) -> None:
    write_text(_active_path(session_id), task_id + "\n")


def clear_active(session_id: str) -> None:
    p = _active_path(session_id)
    if p.exists():
        p.unlink()


def session_tasks(session_id: str) -> list[str]:
    """TASK.md の sessions にこのセッションを含むタスクID（touched の新しい順）。"""
    hits = [t for t in all_tasks() if session_id in (t.get("sessions") or [])]
    hits.sort(key=lambda t: str(t.get("touched", "")), reverse=True)
    return [str(t["id"]) for t in hits]


def resolve_task(task_id: str | None, session_id: str | None) -> str:
    if task_id:
        task_dir(task_id)
        return task_id
    active = get_active(session_id)
    if not active:
        raise HarnessError("タスクIDが指定されておらず、このセッションの現在タスクもありません")
    task_dir(active)
    return active


# ---------------------------------------------------------------- プロジェクト

def project_meta(repo: str) -> dict[str, Value]:
    path = hdir() / "context" / "projects" / f"{repo}.md"
    if not path.exists():
        raise HarnessError(f"プロジェクト文脈がありません: {path}")
    meta, _ = parse_frontmatter(read_text(path))
    return meta


def repo_dir(repo: str) -> Path:
    return harness_root() / "repos" / repo


# ---------------------------------------------------------------- CLI

def run_cli(main_fn: Callable[[], int | None]) -> NoReturn:
    try:
        code = main_fn() or 0
    except HarnessError as e:
        print(f"エラー: {e}", file=sys.stderr)
        code = 2
    sys.exit(code)

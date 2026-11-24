"""journal/INDEX.md を全 TASK.md から再生成する。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402

HEADER = "# タスク索引（自動生成・手で編集しない）"
COLUMNS = "| ID | タイトル | repo | status | touched |\n|---|---|---|---|---|"


def _cell(v) -> str:
    return str(v or "").replace("|", r"\|")


def _table(tasks: list[dict]) -> str:
    rows = [COLUMNS]
    for t in sorted(tasks, key=lambda t: str(t.get("touched", "")), reverse=True):
        rows.append("| " + " | ".join(_cell(t.get(k)) for k in
                                       ("id", "title", "repo", "status", "touched")) + " |")
    return "\n".join(rows)


def render(tasks: list[dict]) -> str:
    open_ = [t for t in tasks if t.get("status") in ("open", "in_progress")]
    closed = [t for t in tasks if t not in open_]
    return (f"{HEADER}\n\n## 未完了\n\n{_table(open_)}\n\n"
            f"## 完了・中止\n\n{_table(closed)}\n")


def write_index() -> Path:
    path = lib.journal_dir() / "INDEX.md"
    lib.write_text(path, render(lib.all_tasks()))
    return path


def main(argv: list[str] | None = None) -> int:
    print(write_index())
    return 0


if __name__ == "__main__":
    lib.run_cli(main)

"""開発タスク・ハーネス（Copilot 版）を、指定フォルダに展開する。

既存のファイルは上書きしない（衝突は一覧にして exit 2）。.gitignore だけは、足りない行を追記する。
git リポジトリでなければ git init する（close_task.py が commit するため）。

使い方: python3 install.py <展開先フォルダ> [--dry-run]
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

PAYLOAD = Path(__file__).resolve().parent.parent / "payload"
SKIP = {"__pycache__"}
RENAME = {"_gitignore": ".gitignore"}
EMPTY_DIRS = ("repos", "_harness/state", "_harness/journal/active")


def plan(target: Path) -> tuple[list[tuple[Path, Path]], list[Path]]:
    """(コピーする組, 衝突する既存ファイル) を返す。"""
    copies, conflicts = [], []
    for src in sorted(PAYLOAD.rglob("*")):
        rel = src.relative_to(PAYLOAD)
        if src.is_dir() or SKIP & set(rel.parts) or src.suffix == ".pyc":
            continue
        dest = target / Path(*[RENAME.get(p, p) for p in rel.parts])
        if dest.name == ".gitignore":
            continue  # 追記で扱う
        (conflicts if dest.exists() else copies).append((src, dest))
    return copies, [d for _, d in conflicts]


def merge_gitignore(target: Path, dry_run: bool) -> list[str]:
    wanted = (PAYLOAD / "_gitignore").read_text(encoding="utf-8").splitlines()
    path = target / ".gitignore"
    have = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    missing = [w for w in wanted if w and w not in have]
    if missing and not dry_run:
        body = "\n".join(have).rstrip("\n")
        path.write_text((body + "\n" if body else "") + "\n".join(missing) + "\n", encoding="utf-8")
    return missing


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("target")
    ap.add_argument("--dry-run", action="store_true", help="何もせず、予定だけ表示する")
    a = ap.parse_args(argv)
    target = Path(a.target).expanduser().resolve()
    if not target.is_dir():
        print(f"展開先フォルダがありません: {target}", file=sys.stderr)
        return 1
    copies, conflicts = plan(target)
    if conflicts:
        print("既存のファイルと衝突するため、何も変更していません:", file=sys.stderr)
        for d in conflicts:
            print(f"  {d.relative_to(target)}", file=sys.stderr)
        return 2
    for src, dest in copies:
        print(f"{'予定' if a.dry_run else '作成'}: {dest.relative_to(target)}")
        if not a.dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
    for d in EMPTY_DIRS:
        if not a.dry_run:
            (target / d).mkdir(parents=True, exist_ok=True)
    for line in merge_gitignore(target, a.dry_run):
        print(f"{'予定' if a.dry_run else '追記'}: .gitignore に {line}")
    if not (target / ".git").exists():
        if a.dry_run:
            print("予定: git init")
        else:
            subprocess.run(["git", "init", "-q", str(target)], check=True)
            print("実行: git init")
    print(f"{len(copies)} ファイルを{'展開予定' if a.dry_run else '展開しました'}: {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

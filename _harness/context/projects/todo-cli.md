---
repo: todo-cli
verify: .venv/bin/pytest -q && .venv/bin/ruff check .
---

# todo-cli

ハーネス練習用の小さな TODO 管理 CLI（`repos/todo-cli`、独立した git リポジトリ）。

## 構成

- `src/todo/cli.py` — argparse のサブコマンド（add / list / done）と各コマンドの処理
- `src/todo/store.py` — JSON ファイルへの保存と読み込み（`TODO_FILE` 環境変数で保存先を変更）
- `src/todo/models.py` — `Task` dataclass
- `tests/` — pytest。`todo_file` fixture が `TODO_FILE` を一時ファイルに向ける

## 課題

`repos/todo-cli/ISSUES.md` に Issue（#1〜#4）がある。

## 検証

repo 直下で `.venv/bin/pytest -q && .venv/bin/ruff check .`（`verify.py` が実行する）。

## 現況

初期状態。

---
id: T-20261124-02
title: delete <id> コマンドを追加する
type: feature
repo: todo-cli
issue: "#2"
status: done
started: 2026-11-24
closed: 2026-11-24
touched: "2026-11-24T22:41:33+09:00"
sessions: [0f2f0cfd-dad2-40a6-aaf2-d080a5e42ed5]
verify: pass
---

# delete <id> コマンドを追加する

## 概要

Issue #2: `delete <id>` コマンドを追加する。

完了の条件:
- `todo delete <id>` で該当タスクが削除・保存され、`削除しました: <id>` を出して exit 0
- 存在しない ID は stderr に `見つかりません: <id>`、exit 1、ファイルは変更しない
- 正常系・異常系のテストがあり、verify（pytest + ruff）が通る
- README の使い方に追記

## 成果

変更点:
- `src/todo/cli.py`: `delete <id>` サブコマンドと `cmd_delete` を追加した。成功時は `削除しました: <id>` を出して exit 0。存在しない ID では stderr に `見つかりません: <id>` を出して exit 1 で、保存しない。
- `tests/test_cli.py`: delete のテストを5本追加した（成功メッセージ、保存結果、エラー出力、ファイル不変、空状態）。
- `README.md`: 使い方に `delete` を追記した。

残課題:
- 採番が max+1 のため、末尾のタスクを削除すると ID が再利用される。挙動を変えるかは別 Issue で判断する。
- ID を指定するコマンドが3つ目になったら、タスク探索を共通ヘルパーに切り出す。

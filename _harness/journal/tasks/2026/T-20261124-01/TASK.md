---
id: T-20261124-01
title: list --sort due が期限なしタスクで落ちる
type: bugfix
repo: todo-cli
issue: "#1"
status: done
started: 2026-11-24
closed: 2026-11-24
touched: "2026-11-24T22:23:06+09:00"
sessions: [4fe85b0c-c76a-46c6-ad4d-ada6de69d394]
verify: pass
---

# list --sort due が期限なしタスクで落ちる

## 概要

ISSUES.md #1: 期限なしのタスクがあると `list --sort due` が TypeError で落ちる。期待動作は「期限なしは末尾に並べる」。

完了の条件:
- 期限あり・なしが混ざっても `list --sort due` が落ちず、期限ありを昇順、期限なしを末尾に並べる
- 同じ期限どうし・期限なしどうしは作成順に並ぶ
- 回帰テストを追加し、verify（pytest + ruff）が exit 0

## 成果

- `src/todo/cli.py`: `list --sort due` のソートキーを `(t.due is None, t.due or date.min, t.created)` に変更した。期限なしは末尾に、同じ順位は作成順に並ぶ。
- `tests/test_cli.py`: 回帰テストを3件追加した（期限なしを末尾に／期限なしどうしは作成順／同じ期限どうしは作成順）。
- commit: close_task.py の出力を参照（メッセージは `T-20261124-01: ...`）。
- 残課題: なし。

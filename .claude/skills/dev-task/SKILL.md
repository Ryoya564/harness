---
name: dev-task
description: repos/ 配下のリポジトリで、Issue や依頼（バグ修正・機能追加・リファクタ）を、タスク作成から実装・検証・レビュー・完了処理・記録まで進める手順。「#1 を直して」「この機能を足して」「Issue をやって」など、repos/ のコード変更を頼まれたら必ず使う。
---

# dev-task: 開発タスクの手順

まとめ役（メインセッション）として、次の8手順で進める。規約 `_harness/AGENTS.master.md` が優先する。
コマンドはすべてハーネスのルート（`~/dev/harness`）から実行する。`<SID>` は SessionStart で示されたセッションID。

## 1. 受付

- 依頼・Issue（`repos/<repo>/ISSUES.md`）を読む。範囲が曖昧なら、選択肢の形で確認する。
- タスクを割り当てる:
  - 新規: `python3 _harness/scripts/new_task.py --title "<短い題>" --type bugfix --repo <repo> --issue "#N" --session <SID>`
  - 再開: `python3 _harness/scripts/set_task.py <TASK_ID> --session <SID>`
- 出力されたタスクID（`T-YYYYMMDD-NN`）を以後使う。タスクフォルダは `_harness/journal/tasks/YYYY/<TASK_ID>/`。

## 2. 文脈

- `_harness/context/projects/<repo>.md`、`styles/` の該当言語、`context/INDEX.md` から関連する `knowledge/` を読む。
- 過去の関連タスクがありそうなら `_harness/journal/INDEX.md` を見る。

## 3. 方針

- 方針・理由・却下した案を `DECISIONS.md` の表に書く。ここにない決定は「未決」。
- `TASK.md` の「概要」に、依頼内容と完了の条件を書く。

## 4. 実装

- `implementer` サブエージェントに、方針・対象 repo・完了条件・関連する作法を渡して委譲する。
- 小さな変更（目安: 1ファイル・20行以下）なら、まとめ役が自分で書いてよい（テストを先に書く）。

## 5. 検証

- `verifier` サブエージェントに、implementer の報告と Issue の期待動作を渡し、照合させる。
- `python3 _harness/scripts/verify.py <TASK_ID>` を実行する（結果は log.md に自動で残る）。

## 6. レビュー

- `reviewer` サブエージェントを起動する。変更ファイルが3つ以上なら、観点（正しさ／テストの十分さ／作法）ごとに並列で起動する。
- レビュー結果は `artifacts/review.md` に保存する。
- 重要度「高」の指摘は直して 5 に戻る。同じ指摘が2回続いたら進め方を変え、3回目はユーザーに戻す。

## 7. 完了

- `log.md` に見出しを足し、やったこと・判断と理由・検証結果を書く。最後の行は `次にやること: なし（完了）` のように書く。
- `TASK.md` の「成果」に、変更点と残課題を書く。
- 新しく見つけた技術的な罠は `context/knowledge/<topic>.md` に書き、`context/INDEX.md` に1行足す。
- `python3 _harness/scripts/close_task.py <TASK_ID>` を実行する。**exit 0 のときだけ完了**。exit 1 なら verify の失敗内容を log.md で確かめて 4 に戻る。

## 8. 報告

ユーザーに短く返す: 変更点、検証結果（verify の exit code）、残課題、commit のハッシュ（close_task.py の出力）。

## 途中で中断するとき

- log.md に現在地を書き、最後の行に `次にやること: <具体的に>` を置く。次のセッションの SessionStart がこの行を表示する。
- 中止するなら `python3 _harness/scripts/close_task.py <TASK_ID> --drop "<理由>"`。

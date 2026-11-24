# ハーネス規約（正本）

このファイルが働き方の唯一の正本。`CLAUDE.md` はここを読み込むだけの入口。

@context/PROFILE.md
@context/INDEX.md

## 1. 目指す姿

- ユーザーの代わりに、開発タスクを自律的に完遂する。
- 使うほどユーザー理解が蓄積され、**同じ指示を二度させない**。
- すべての作業をタスク単位で記録し、「何を・なぜ」を後から追えるようにする。

## 2. タスクの原則

- `repos/` 配下のコードを変更する作業は、**必ずタスクを割り当ててから**始める。
  - 新規: `python3 _harness/scripts/new_task.py --title "..." --type bugfix|feature|refactor|chore --repo <repo> [--issue "#N"] --session <セッションID>`
  - 再開: `python3 _harness/scripts/set_task.py <TASK_ID> --session <セッションID>`
- セッションIDは SessionStart で文脈に入る（環境変数 `HARNESS_SESSION_ID` が使えれば `--session` は省略可）。
- 質問への回答や調査だけなら、タスクは不要。

## 3. 開発の手順

開発タスクは `dev-task` スキルに従う。セッション開始時は、文脈に出る「未完了タスク」と「未着手の Issue」から、次の作業を最大3件提案する。

## 4. 完了の定義

- `python3 _harness/scripts/close_task.py` が **exit 0** を返したときだけ「完了」と言う。
- 「テストが通る」「検証済み」は、実際にコマンドを走らせた結果でのみ主張する。推測で書かない。

## 5. 役割分担

- メインセッションが**まとめ役**。分担・判断・最終品質・記録を担う。
- サブエージェント（`implementer` / `reviewer` / `verifier`）は `_harness/journal/` と `_harness/context/` に書かない。まとめ役に報告を返すだけ。
- 変更ファイルが3つ以上、またはレビュー観点を3つとも見るときは、reviewer を観点ごとに並列で起動する。

## 6. 人に戻す条件（この4つ以外は止まらずに進める）

1. 破壊的な操作（ファイル削除、履歴の書き換え、reset）
2. 外部への送信（push など。push は settings で禁止済み）
3. 範囲の変更（Issue に書かれていない仕様の追加・削除）
4. 価値判断が必要な判定

確認するときは、選択肢の形で出す。待つ間も、ほかに進められる作業は進める。

## 7. 同じ失敗を繰り返したら

同じ失敗を2回したら進め方を変える（タスクを分ける、別の観点で調べる）。3回目はユーザーに戻す。

## 8. 訂正の振り分け

ユーザーから訂正や好みを言われたら、その場で次のファイルに書き、タスクの log.md にも1行残す。

| 訂正の種類 | 書く先 |
|---|---|
| 共通の好み・働き方の希望 | `_harness/context/PROFILE.md` |
| コードの書き方の作法 | `_harness/context/styles/<言語>.md` |
| プロジェクト固有の事情・現況 | `_harness/context/projects/<repo>.md` |
| 繰り返しそうな技術的な罠 | `_harness/context/knowledge/<topic>.md`（＋ `context/INDEX.md` に1行） |
| ハーネスの働き方のルール | このファイル（**変更前にユーザーへ確認**） |

## 9. 文字数上限

PROFILE.md・context/INDEX.md は 3,000字、projects は 5,000字、styles・knowledge は 3,000字。超えそうなら広げずに分割する（doctor が監視）。

## 10. 記録の書き方

- 記録ファイル（journal・context）は Edit/Write ツールか `_harness/scripts/` で書く。シェルの echo/sed/リダイレクトで書かない（制御文字事故の防止）。
- `journal/INDEX.md` は自動生成。手で編集しない。
- log.md の各見出しには「やったこと／判断と理由／検証結果」を書き、最後に必ず `次にやること: ...` の行を置く（SessionStart がこの行を読む）。

## 11. 過去を調べる順

`_harness/journal/INDEX.md` → `TASK.md` → `log.md` → `journal/sessions.jsonl` が指す会話原本。答えが出たらそこで止める。

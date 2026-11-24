# 開発タスク・ハーネス（GitHub Copilot / VS Code 版）

VS Code の Copilot エージェントに、開発タスク（Issue → 実装 → テスト → 完了）を任せるためのハーネス。
ワークスペースのルートに置いて使う。

## 使い方

1. このフォルダを VS Code で開き、ワークスペースを信頼する。
2. Chat を開き、Copilot のエージェントで「repos/<repo> の #1 を直して」のように頼む。
3. 開始時に sessionStart hook が、ユーザーの好み・未完了タスク・未着手 Issue を渡す。
4. 開発の手順は `.github/skills/dev-task/SKILL.md`。完了は `close_task.py` の exit 0 だけ。

## 構成

| 責務 | 置き場所 |
|---|---|
| 規約（どう働くか） | `.github/copilot-instructions.md`（Copilot が自動で読む） |
| 手順 | `.github/skills/dev-task/`、`.github/skills/harness-doctor/` |
| 役割 | `.github/agents/`（implementer・reviewer・verifier） |
| 自動処理 | `.github/hooks/harness.json` → `_harness/hooks/*.py` |
| 文脈 | `_harness/context/`（PROFILE・INDEX は hook が毎回渡す） |
| 記録 | `_harness/journal/`（tasks/YYYY/<ID>/ に TASK.md・log.md・DECISIONS.md） |
| 実行 | `_harness/scripts/`（new_task / set_task / verify / close_task / build_index / doctor） |

## hook

| イベント | スクリプト | 役割 |
|---|---|---|
| sessionStart | `session_start.py` | 常に読む文脈・前回の続き・未着手 Issue を渡す。doctor を週1回実行 |
| agentStop | `stop_check.py` | 返答を終えるたびに検査し、記録漏れがあれば差し戻す（同じ状態では1回だけ） |
| sessionEnd | `session_end.py` | 会話原本の場所を `journal/sessions.jsonl` に記録する |
| preToolUse | `guard.py` | `git push` と `rm -rf` をシェル実行の前に止める |

hook は VS Code ではプレビュー機能。読み込まれているかは、Chat で `/hooks` を入力するか Agent Customizations エディタで確かめる。

## Claude Code 版との違い

- 規約は `.github/copilot-instructions.md` に直接書く（Copilot は指示ファイル内の参照をたどらない）。
- PROFILE.md と context/INDEX.md の本文は sessionStart hook が渡す。
- 許可・禁止のリストがないため、`git push` と `rm -rf` は preToolUse hook で止める。
- 会話ログの形式が公開されていないため、記録漏れの検出は git の変更（セッション開始後に変わったファイル）だけで行う。
- sessionEnd に会話原本のパスが来ないため、agentStop で控えた値を使う。
- サブエージェントのモデルは指定していない（まとめ役と同じモデルになる）。変えたいときは `.github/agents/*.agent.md` の frontmatter に `model:` を足す。

## Windows

hook のコマンドは `python3` を使う。Windows で `python3` がない場合は、`.github/hooks/harness.json` の各 `command` を `python` か `py -3` に変える。

## テスト

```bash
python3 -m unittest discover -s _harness/tests -t .
python3 _harness/scripts/doctor.py --selftest
```

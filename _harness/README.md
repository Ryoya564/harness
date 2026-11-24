# 開発タスク・ハーネス

Claude Code で開発タスク（Issue → 実装 → テスト → 完了）を任せるためのハーネス。
参考: [NTT DATA TECH の記事](https://zenn.dev/nttdata_tech/articles/9562962cc181a1)。詳細設計は `docs/superpowers/specs/2026-11-24-dev-harness-design.md`。

## 使い方

```bash
cd ~/dev/harness && claude
# 例: 「ISSUES.md の #1 を直して」
```

- 初回起動時は信頼ダイアログを承認する（未承認だと settings.json の permissions が無視される）。
- SessionStart hook が、未完了タスク・未着手 Issue・doctor の要約を最初に示す。
- 開発の手順は `.claude/skills/dev-task/SKILL.md`。完了は `close_task.py` の exit 0 だけ。
- 記録漏れのまま終わろうとすると、Stop hook が止める（同じ状態では1回だけ）。

## 5つの責務

| 責務 | 置き場所 |
|---|---|
| 規約（どう働くか） | `AGENTS.master.md`（入口は `/CLAUDE.md` の1行） |
| 文脈（ユーザーと状況の理解） | `context/`（PROFILE・INDEX は常に読む。projects/styles/knowledge は必要時） |
| 記録（何をしたか、なぜ） | `journal/`（tasks/YYYY/<ID>/ に TASK.md・log.md・DECISIONS.md） |
| 検査（壊れていないか） | `scripts/doctor.py`（SessionStart で週1回自動実行） |
| 実行（決定的な処理） | `scripts/`（new_task / set_task / verify / close_task / build_index） |

## ループと、その終わりの決め方

| ループ | 終わり |
|---|---|
| 完遂ループ（1タスク） | `close_task.py` が exit 0（verify コマンドが成功） |
| セッションループ | Stop hook の検査を通過 |
| 訂正ループ | 振り分け先のファイルと INDEX を更新 |
| 改善ループ | doctor の NG/WARN をユーザーと判断 |

## テスト

```bash
python3 -m unittest discover -s _harness/tests -t .
python3 _harness/scripts/doctor.py --selftest
```

## 採らなかった案

- **グローバル配置（`~/.claude/` に規約や hooks を置く）**: このハーネスはプロジェクトフォルダ内で完結させる方針。グローバル設定を汚さず、フォルダごと持ち運べて、試行錯誤しても他のプロジェクトに影響しない。
- **台帳 registry/**: 扱うリポジトリが1つのうちは不要。repo と verify コマンドの対応は `context/projects/<repo>.md` の frontmatter で足りる。
- **共有ボード（board.jsonl / BOARD.md）**: サブエージェントは3役で、まとめ役が順に呼ぶため、状態は log.md で追える。並列ワーカーが10を超えるようになったら検討する。
- **skill-mining・週次 harness-review**: 記録が数十タスク貯まるまで、掘り起こす材料がない。
- **更新のないタスクの自動クローズ**: 誤って閉じたときの影響が大きい（記事 11 章）。doctor が7日放置を WARN で知らせるだけにした。
- **DB を記録の正本にする**: 差分を人が読めて git で追えるテキスト（Markdown / JSONL）を選んだ。
- **常駐プロセス・cron**: 周期処理（doctor の週次実行）は SessionStart で前回の実行時刻を見て行う。PC を毎日シャットダウンしても確実に動く。

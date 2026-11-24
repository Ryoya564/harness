# 開発タスク・ハーネス 設計書

- 作成日: 2026-11-24
- 参考: https://zenn.dev/nttdata_tech/articles/9562962cc181a1 （以下「記事」）
- 実行環境: WSL2 (Linux) / Claude Code 2.1.x / Python 3.12（pytest・ruff・jq は未インストール）

## 1. 目的と背景

記事の「モデルの外側でAgentを動かす仕組み（ハーネス）」を、Claude Code だけで動く**プログラマー向け**の形で作り、実際に回して学ぶ。

題材は「開発タスク（Issue → 実装 → テスト → 完了）を任せる」こと。記事の芯である次の4点を、開発の文脈で一通り体験できることを狙う。

- **規約**：働き方の正本を1か所に置き、入口は薄くする
- **記録**：タスク単位（task-first）で「何を・なぜ」を残す
- **文脈**：訂正や罠が上限付きファイルに蓄積し、同じ指示を二度させない
- **検査**：完了は機械（テスト・lint の exit 0）で判定し、ハーネス自身の故障は doctor で即わかる

## 2. ゴール / 非ゴール / アンチゴール

**ゴール**
- `~/dev/harness` で Claude Code を起動し「ISSUES.md の #1 をやって」と頼むと、タスク作成 → 実装 → 検証 → レビュー → 完了処理 → 記録まで進む。
- 次のセッションを開くと、前回の続き（未完了タスク・現在地）が自動で提示される。
- 記録漏れのまま終わろうとすると Stop hook が1回だけ止める。
- ユーザーの訂正が規約どおりの振り分け先ファイルに書かれ、以後のセッションで効く。
- `harness-doctor` がハーネスの破損（hook 未登録、frontmatter 破損、文字数超過など）を報告し、`--selftest` で検査自体が機能することを確認できる。

**非ゴール**
- グローバル設定（`~/.claude/`）への配置。すべてプロジェクトフォルダ内で完結させる。
- Codex 対応、Windows/PowerShell 対応。
- 記事の台帳（registry/）、共有ボード（board.jsonl）、skill-mining、週次 harness-review、子ハーネス。
- リモートへの push、PR 作成など外部への送信。

**アンチゴール**（動いても失敗とみなす状態）
- hook が何度もブロックし続け、作業の邪魔になる。
- テストを実際に走らせずに「完了」「検証済み」と記録される。
- 仕組みが複雑すぎて、ユーザーがファイルを読んでも何が起きているか追えない。

## 3. 制約

- グローバル設定を作らない。Claude Code は `~/dev/harness` をカレントにして起動する前提。
- hook・スクリプトは **Python 標準ライブラリのみ**（jq なし。ハーネス側に外部依存を持ち込まない）。
- ハーネス自身のテストは `python3 -m unittest`（pytest に依存しない）。
- 練習リポジトリの依存（pytest, ruff）は、そのリポジトリの `.venv` にだけ入れる。
- ハーネス文書は日本語で書く。
- 記録ファイルの書き込みは、Python スクリプトか Edit/Write ツールで行う。シェルの echo や sed では書かない（記事 11 章の制御文字事故への対策）。

## 4. 検討した案と選択

| 案 | 内容 | トレードオフ |
|---|---|---|
| 1. 最小構成 | 規約＋TASK/log＋PROFILE＋3 hooks | 速いが、分担と自己診断がない |
| **2. 中くらいの構成（採用）** | 1 ＋ サブエージェント（implementer/reviewer/verifier）＋ harness-doctor ＋ DECISIONS/knowledge | 記事の芯を一通り体験できる。練習用として重すぎない |
| 3. 記事を全部再現 | 2 ＋ registry、board、skill-mining、週次診断、子ハーネス | 記事に忠実だが、練習リポジトリ1つでは使う場面がない |

ユーザーが案2を選んだ。題材は、開発タスク／コードレビュー／技術調査の3候補から「開発タスク」をユーザーが選んだ（完了を機械で判定でき、記事の考え方を素直に再現できるため）。

## 5. 全体構成

```
~/dev/harness/                      # ハーネス本体。単独の git リポジトリ
├─ CLAUDE.md                        # 1行: @_harness/AGENTS.master.md
├─ .gitignore                       # repos/ を除外
├─ .claude/
│  ├─ settings.json                 # hooks 登録・permissions
│  ├─ agents/
│  │  ├─ implementer.md
│  │  ├─ reviewer.md
│  │  └─ verifier.md
│  └─ skills/
│     ├─ dev-task/SKILL.md          # 開発タスクの手順（開始〜完了）
│     └─ harness-doctor/SKILL.md    # doctor の実行と結果の読み方
├─ _harness/
│  ├─ AGENTS.master.md              # 規約の正本
│  ├─ README.md                     # 設計の要約と「採らなかった案」
│  ├─ context/
│  │  ├─ PROFILE.md                 # 常に読む。上限 3,000字
│  │  ├─ INDEX.md                   # 常に読む。context の目次。上限 3,000字
│  │  ├─ projects/todo-cli.md       # 必要時に読む。上限 5,000字。frontmatter に verify コマンド
│  │  ├─ styles/python.md           # 書き方の作法。上限 3,000字
│  │  └─ knowledge/                 # 罠・how-to。1ファイル上限 3,000字
│  ├─ journal/
│  │  ├─ INDEX.md                   # 全タスク索引（スクリプト生成。手で編集しない）
│  │  ├─ sessions.jsonl             # セッション原本の所在
│  │  ├─ active/<session_id>        # このセッションの現在タスクID（1行）
│  │  └─ tasks/YYYY/<TASK_ID>/
│  │     ├─ TASK.md                 # 正本（frontmatter＋概要）
│  │     ├─ log.md                  # 経緯（作業・判断・検証結果を追記）
│  │     ├─ DECISIONS.md            # 設計判断の台帳（ここにない決定は「未決」）
│  │     └─ artifacts/              # レビュー結果など
│  ├─ hooks/
│  │  ├─ session_start.py
│  │  ├─ stop_check.py
│  │  └─ session_end.py
│  ├─ scripts/
│  │  ├─ lib.py                     # frontmatter 読み書き・パス解決など共通処理
│  │  ├─ new_task.py
│  │  ├─ set_task.py                # 既存タスクをこのセッションの現在タスクにする
│  │  ├─ verify.py
│  │  ├─ close_task.py
│  │  ├─ build_index.py
│  │  └─ doctor.py
│  ├─ templates/                    # TASK.md / log.md / DECISIONS.md の雛形
│  ├─ state/                        # doctor の前回実行時刻など（git 管理外）
│  └─ tests/                        # unittest（hooks・scripts・doctor）
├─ docs/superpowers/specs/          # 本設計書
└─ repos/
   └─ todo-cli/                     # 練習リポジトリ（独立した git。harness 側では ignore）
```

**git の扱い**: `~/dev/harness` を git リポジトリにし、`_harness/`（journal を含む）、`.claude/`、`CLAUDE.md`、`docs/` を管理する。`repos/` と `_harness/state/` は `.gitignore` に入れる。`repos/todo-cli` はそれ自体が独立した git リポジトリ。

## 6. 規約（AGENTS.master.md）の中身

入口は `CLAUDE.md` の1行 `@_harness/AGENTS.master.md` だけ。正本の冒頭で `@context/PROFILE.md` と `@context/INDEX.md` を取り込む（常に読む層）。

正本に書く内容:

1. **目指す姿**: ユーザーの代わりに開発タスクを自律的に完遂する。使うほどユーザー理解が蓄積され、同じ指示を二度させない。すべての作業をタスク単位で記録する。
2. **タスクの原則**: `repos/` 配下のコードを変更する作業は、必ずタスク（`new_task.py` か `set_task.py`）を割り当ててから始める。質問への回答や調査だけならタスクは不要。
3. **開発の手順**: `dev-task` スキルに従う（スキルの中身は §9）。
4. **完了の定義**: `close_task.py` が exit 0 を返したときだけ「完了」と言う。検証は「実際にコマンドを走らせた結果」でのみ主張する。
5. **役割分担**: メインセッションがまとめ役となり、分担・判断・最終品質・記録を担う。サブエージェントは journal と context に書かない。まとめ役への報告だけを返す。
6. **人に戻す条件**（この4つ以外は止まらずに進める）: 破壊的な操作（ファイル削除、履歴の書き換え）、外部への送信（push など）、範囲の変更（Issue に書かれていない仕様の追加・削除）、価値判断が必要な判定。確認は選択肢の形で出す。
7. **同じ失敗を2回したら**: 進め方を変える（タスクを分ける、別の観点で調べる）。3回目はユーザーに戻す。
8. **訂正の振り分け表**: ユーザーから訂正や好みを言われたら、その場で次のファイルに書き、log.md にも1行残す。

   | 訂正の種類 | 書く先 |
   |---|---|
   | 共通の好み・働き方の希望 | context/PROFILE.md |
   | コードの書き方の作法 | context/styles/<言語>.md |
   | プロジェクト固有の事情・現況 | context/projects/<repo>.md |
   | 繰り返しそうな技術的な罠 | context/knowledge/<topic>.md（＋ context/INDEX.md に1行） |
   | ハーネスの働き方のルール | AGENTS.master.md（変更前にユーザーへ確認） |

9. **文字数上限**: 上限を超えそうなら、広げずに分割する（doctor が監視）。
10. **記録の書き方**: 記録ファイルは Edit/Write ツールか `_harness/scripts/` で書く。シェルの echo/sed で書かない。
11. **過去を調べる順**: journal/INDEX.md → TASK.md → log.md → sessions.jsonl が指す会話原本。答えが出たらそこで止める。

## 7. タスクの記録

**タスクID**: `T-YYYYMMDD-NN`（その日の連番、2桁）。

**TASK.md の frontmatter**（YAML 風の単純な `key: value`。リストはフロー形式 `[a, b]`。パーサは lib.py に自前で持つ）

```yaml
id: T-20261124-01
title: list --sort due が期限なしタスクで落ちる
type: bugfix            # feature | bugfix | refactor | chore
repo: todo-cli          # repos/ 配下のディレクトリ名
issue: "#1"             # 任意
status: in_progress     # open | in_progress | done | dropped
started: 2026-11-24
closed:                 # done/dropped にしたとき
touched: 2026-11-24T21:40:00+09:00
sessions: [<session_id>, ...]
verify: pass            # 最後の verify 結果: pass | fail | none
```

状態は `status` だけで管理し、フォルダは移動しない（記事と同じ）。

**log.md**: 時刻つきの見出しごとに「やったこと／判断と理由／検証結果／次にやること」を追記する。`verify.py` と `close_task.py` も結果をここに自動で追記する。

**DECISIONS.md**: 「決定 / 理由 / 却下した案」の表。タスク開始時は空の雛形。

**journal/INDEX.md**: `build_index.py` が全 TASK.md から生成する。未完了タスクを先頭に、ID・タイトル・repo・status・touched の表にする。

## 8. スクリプト

すべて `python3 _harness/scripts/<name>.py`。ハーネスのルートは、スクリプト自身の位置から求める（cwd に依存しない）。

| スクリプト | 役割 | 終了コード |
|---|---|---|
| `new_task.py --title T --type bugfix --repo todo-cli [--issue "#1"] [--session ID]` | タスクフォルダと3ファイルを雛形から作り、`active/<session>` に書き、INDEX を再生成し、ID を標準出力に出す | 0 / 引数不正・repo なしは 2 |
| `set_task.py <TASK_ID> [--session ID]` | 既存タスクを現在タスクにし、sessions に追加し、status を in_progress にする | 0 / 未存在は 2 |
| `verify.py [<TASK_ID>]` | projects/<repo>.md の frontmatter `verify:` を repo ディレクトリで実行する。出力の末尾40行と終了コードを log.md に追記し、TASK.md の `verify` を更新する | verify コマンドの終了コードをそのまま返す |
| `close_task.py [<TASK_ID>] [--drop "理由"]` | verify を実行し、成功した場合だけ以下を行う。<br>・status=done と closed を設定する<br>・repo でローカル commit する（メッセージにタスクIDとタイトルを入れる）<br>・active を解除する<br>・INDEX を再生成する<br>・**ハーネス側でも** `_harness/journal/` と `_harness/context/` の変更だけを commit する（メッセージは `journal: <TASK_ID> close`）<br>どちらの commit も push しない。`--drop` は verify せずに dropped にする（ハーネス側の commit は同様に行う） | 0 / verify 失敗は 1（status は変えない） |
| `build_index.py` | journal/INDEX.md を再生成する | 0 |
| `doctor.py [--selftest] [--quiet]` | §11 の検査 | NG があれば 1、なければ 0 |

`--session` を省略したときは環境変数 `HARNESS_SESSION_ID` を使う（§10 の SessionStart で設定）。TASK_ID を省略したときは、そのセッションの active タスクを使う。

## 9. サブエージェントとスキル

### サブエージェント（.claude/agents/）

| 名前 | 役割 | モデル | ツール |
|---|---|---|---|
| implementer | まとめ役が決めた方針どおりに repo を変更し、テストを書き、変更点・実行したコマンドと結果・未解決点を報告する | sonnet | Read, Edit, Write, Bash, Grep, Glob |
| reviewer | 差分（`git diff`）を、指定された観点（正しさ／テストの十分さ／作法 styles/）で読み、指摘を重要度つきで返す。コードは変更しない | sonnet | Read, Bash, Grep, Glob |
| verifier | implementer の報告にある主張（「テストが通る」「ファイルを追加した」など）を、自分でコマンドを走らせて1つずつ照合し、確認済み／不一致／未確認を返す | sonnet | Read, Bash, Grep, Glob |

共通のルール（各定義の本文に書く）: journal/ と context/ には書かない。ファイルを作ったと報告する前に、存在を `ls` で確かめる。報告は決まった見出し（変更点／実行したコマンドと結果／未解決）で返す。

並列化: 変更ファイルが3つ以上、またはレビュー観点を3つとも見るときは、reviewer を観点ごとに並列で起動する。

### dev-task スキル（.claude/skills/dev-task/SKILL.md）

1. **受付**: Issue／依頼を読み、範囲が曖昧なら選択肢の形で確認する。`new_task.py`（既存タスクの再開なら `set_task.py`）。
2. **文脈**: context/projects/<repo>.md、styles、関連する knowledge を読む。
3. **方針**: 方針と、却下した案を DECISIONS.md に書く。
4. **実装**: implementer に委譲する。小さな変更（目安1ファイル・20行以下）ならまとめ役が自分で書いてもよい。
5. **検証**: verifier に implementer の報告を照合させ、`verify.py` を実行する。
6. **レビュー**: reviewer を起動し、重要度「高」の指摘は直して 5 に戻る。同じ指摘が2回続いたら進め方を変える。
7. **完了**: log.md に要約を書き、`close_task.py` を実行する。exit 0 で完了。新しい罠を見つけたら knowledge に書く。
8. **報告**: ユーザーに、変更点・検証結果・残課題・commit のハッシュを短く返す。

### harness-doctor スキル

`doctor.py` を実行し、NG/WARN の読み方を示す。doctor は報告だけで、自動で直さない。直すかどうかはユーザーと決める。

## 10. hooks（.claude/settings.json）

3つとも `python3 "$CLAUDE_PROJECT_DIR/_harness/hooks/<name>.py"` を command として登録する。入力は stdin の JSON（session_id, transcript_path, stop_hook_active など）。

**SessionStart**（止めない）
- `CLAUDE_ENV_FILE` が渡されていれば `export HARNESS_SESSION_ID=<id>` を書き込む。
- `additionalContext` に次を出す: セッションID（環境変数が使えない場合に備えて、スクリプトへ `--session` で渡すよう明記）、未完了タスクの一覧（ID・タイトル・log.md の最後の「次にやること」）、doctor の要約。
- doctor は前回の実行から7日経っていれば実行し、NG/WARN の件数と上位5行を出す（常駐プロセスや cron は使わない）。
- 規約にある「次の作業を最大3件提案」の材料として、未完了タスクと repo の ISSUES.md 未着手項目を並べる。

**Stop**（記録漏れがあれば止める。ただし同じ記録漏れで止めるのは1回だけ）
- `stop_hook_active` が true なら、何もせず通す（無限ブロック防止）。
- 次のどれかに当たれば `{"decision":"block","reason":"<チェックリスト>"}` を返す。
  - a. このセッションで `repos/` 配下を変更したのに active タスクがない。判定には2つの情報を使う。1つは transcript に残る Edit/Write/NotebookEdit で、もう1つは `repos/*` の `git status --porcelain` に出る変更である。サブエージェントの編集は transcript に残らないので、git status で補う。
  - b. active タスクがあり、次の両方に当たる。
    - repo の作業ツリーで変更されたファイルの最新 mtime が、log.md の mtime より新しい
    - log.md が 30 分以上更新されていない（記事と同じ 30 分の基準。作業途中の毎ターンでは止めない）
  - c. active タスクの TASK.md の sessions に、このセッションIDがない
- **同じ状態で何度も止めない**: 止めるときは「当たった条件とその状態の指紋」を `_harness/state/stop-blocks.json` に session_id ごとに保存する。指紋は、条件 a・b なら変更ファイル一覧と各 mtime のハッシュ、条件 c ならタスクID である。同じ指紋ではもう止めない。新しく変更が加わって指紋が変わったときだけ、再び止める。人に選択肢で確認している最中でも、毎ターン止まることはない。
- reason は、満たしていない項目だけを箇条書きにする（log.md への追記、タスクの作成と割り当て、完了なら close_task.py）。
- どれにも当たらなければ通す。スクリプト内で例外が起きても通し（exit 0）、エラーは `_harness/state/hook-errors.log` に書く（doctor が拾う）。

**SessionEnd**（止められない）
- `sessions.jsonl` に `{session_id, transcript_path, ended_at, reason, task_id}` を追記する。同じ session_id はタイムスタンプが新しいほうで置き換える（全行を読んで重複を除く）。
- active タスクがあれば TASK.md の `touched` を更新する。`active/<session_id>` は削除しない（同じセッションを再開したときのため）。

**permissions**（settings.json）
- allow: `python3 _harness/scripts/*`, `python3 _harness/hooks/*`, `.venv/bin/pytest`, `.venv/bin/ruff`, `git status/diff/log/add/commit`（ハーネス側・repo 側の両方）
- deny: `git push`, `rm -rf`

## 11. harness-doctor の検査

出力は1行ごとに `NG|WARN|INFO  <何が>  <どこで>  <どうすればよいか>`、最後に件数の集計。

**NG**
- settings.json に3つの hook が登録されていない、または参照先のスクリプトがない
- TASK.md の frontmatter が読めない、または必須キー（id, title, type, repo, status, started）が欠けている
- journal/ と context/ の .md / .jsonl に制御文字（`\t` と改行以外の U+0000〜U+001F）がある
- 常に読む層（PROFILE.md, context/INDEX.md）が上限を超えている
- projects/<repo>.md に `verify:` がない、または repo ディレクトリがない
- status=done なのに verify≠pass

**WARN**
- in_progress のまま touched から7日以上経っている
- 必要時に読む層（projects, styles, knowledge）が上限を超えている
- journal/INDEX.md の記載が TASK.md の実態と食い違う（再生成で直る）
- sessions.jsonl に記録されているのに、どのタスクの sessions にも入っていないセッション（タスクなしの作業。INFO 寄りだが件数が多いときに気づくため）
- `.claude/skills/*/SKILL.md` の description が 1,024 字を超えている
- `_harness/state/hook-errors.log` に新しいエラーがある

**INFO**: タスク件数（状態別）、最後の doctor 実行時刻

**--selftest**: 一時ディレクトリに壊した雛形（frontmatter の欠損、制御文字、上限超過、hook 未登録）を作り、該当する NG/WARN がすべて出ることを確かめる。1つでも出なければ exit 1。記事の「わざと故障を起こして検知を確かめる」に相当する。

## 12. 練習リポジトリ repos/todo-cli

**中身**: Python 製の TODO 管理 CLI。保存先は JSON ファイル（既定は `~/.todo-cli.json`。環境変数 `TODO_FILE` で変えられる。テストは tmp_path を使う）。

```
python -m todo add "牛乳を買う" --due 2026-12-01
python -m todo list [--sort due|created]
python -m todo done <id>
```

**構成**: `pyproject.toml`（ruff の設定を含む）、`src/todo/`（`__main__.py`, `cli.py`, `store.py`, `models.py`）、`tests/`、`README.md`、`ISSUES.md`、`.venv`（pytest と ruff）。

**初期状態**: 既存のテストはすべて通り、ruff も通る。そのうえで、わざと次のバグを1つ入れておく（テストでは捕まえていない）。

**ISSUES.md**（ハーネスに任せるお題）
- #1 [bug] 期限なしのタスクがあると `list --sort due` が TypeError で落ちる（期限なしは末尾に並べるのが期待動作）
- #2 [feature] `delete <id>` コマンドを追加する
- #3 [feature] 優先度（high/medium/low、既定 medium）を持たせ、`list --priority high` で絞り込めるようにする
- #4 [feature] `export --format markdown` でチェックリスト形式で出力する

**projects/todo-cli.md** の frontmatter: `verify: .venv/bin/pytest -q && .venv/bin/ruff check .`

## 13. 受け入れ確認

1. `python3 -m unittest discover _harness/tests` がすべて通る（hooks には偽の stdin JSON を与えて検証する）。
2. `doctor.py --selftest` が exit 0、`doctor.py` が NG 0 件。
3. 練習リポジトリで verify コマンドが exit 0。
4. **実地の確認**: `~/dev/harness` で Claude Code を起動し、「ISSUES.md の #1 を直して」と頼む。タスク作成 → 修正 → 検証 → レビュー → close（commit）まで進み、log.md・INDEX.md・sessions.jsonl に記録が残ることを確かめる。
   - ビルダーは事前確認として、ハーネス一式を**使い捨てのコピー**（scratchpad）に複製し、そこで `claude -p` を非対話で実行して #1 を通す。本物の `~/dev/harness` は初期状態のまま残す。こうすれば、reset や journal の削除といった破壊的な後始末が要らない。
   - 最終的な確認は、ユーザーが本物の `~/dev/harness` で対話セッションを開いて行う。
5. Stop hook の確認（unittest で偽の stdin と一時 git repo を使う）:
   - 記録漏れの状態で1回止まる。
   - `stop_hook_active=true` なら通る。
   - 同じ状態（同じ指紋）では2回目に止まらない。
   - 新しい変更が加わると、再び止まる。
   - log.md の更新から 30 分以内なら止まらない。

## 14. ビルダーに任せること

- lib.py の frontmatter パーサの細部、log.md の見出しの細かな書式
- サブエージェント定義とスキルの文面（§9 の役割とルールを満たしていればよい）
- 練習リポジトリのコードの中身とテストの粒度（§12 を満たしていればよい）
- PROFILE.md の初期内容（空に近い雛形でよい。「確認は選択肢で」「次の作業を最大3件提案」程度）
- `_harness/README.md` の採らなかった案には、少なくとも次を書く: グローバル配置、registry、board、skill-mining、自動クローズ（記事 11 章の理由）、DB を正本にする案

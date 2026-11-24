---
name: harness-setup
description: VS Code の GitHub Copilot エージェント向けに「開発タスク・ハーネス」（規約・タスク記録・サブエージェント3役・hook・完了判定スクリプト）をワークスペースに構築する。「ハーネスを作って」「開発ハーネスをセットアップ」「タスク管理の仕組みを入れて」と頼まれたとき、またはハーネスの repo 追加・初期設定を頼まれたときに使う。
argument-hint: "[展開先フォルダ（省略時はワークスペースのルート）]"
---

# harness-setup: 開発タスク・ハーネスを構築する

Copilot エージェントに開発タスクを任せるためのハーネスを、ワークスペースに組み立てる。
ファイルの展開は [install.py](scripts/install.py) が決まった手順で行う。エージェントは、利用者への確認と初期設定を担当する。

展開されるものの全体像は [payload/_harness/README.md](payload/_harness/README.md) を読む。

## 前提

- 展開先は **VS Code で開いているワークスペースのルート**にする。hook はワークスペースのルートを基準にスクリプトを探すので、サブフォルダに置くと動かない。
- `python3`（3.10 以上）と `git` が使えること。先に `python3 --version` と `git --version` で確かめる。

## 手順

### 1. 展開先を決める

- 引数があればそのフォルダ、なければワークスペースのルートを展開先にする。
- 展開先がワークスペースのルートでない場合は、上の前提を説明し、利用者に選択肢で確認する。

### 2. 予定を見せる

このスキルのフォルダ（この SKILL.md があるフォルダ）の絶対パスを `<SKILL_DIR>` として、次を実行する。

```bash
python3 <SKILL_DIR>/scripts/install.py <展開先> --dry-run
```

- exit 0: 作成予定のファイル一覧を利用者に短く示し、手順 3 に進む。
- exit 2: 既存ファイルと衝突している。**上書きしない**。衝突したファイルを示し、「別のフォルダに展開する／衝突したファイルを利用者が退避してから再実行する／中止する」を選択肢で確認する。ファイルの削除や移動を自分で行わない。

### 3. 展開する

```bash
python3 <SKILL_DIR>/scripts/install.py <展開先>
```

`git init` が必要なら install.py が行う。

### 4. 管理する repo を登録する

利用者に、ハーネスで扱うリポジトリを聞く（あとで足すこともできる）。repo ごとに次を行う。

1. `repos/<repo>/` に置いてもらう（clone するか、既存のフォルダを移す）。`repos/` は .gitignore 済みで、各 repo は独立した git リポジトリのまま扱う。
2. 完了判定に使う **verify コマンド**（テストと lint を1行で。例: `.venv/bin/pytest -q && .venv/bin/ruff check .`）を聞く。repo の README や設定ファイルから推測できる場合は、案を選択肢で示す。
3. `_harness/context/projects/<repo>.md` を作る。frontmatter の `repo:` と `verify:` は必須。

   ```markdown
   ---
   repo: <repo>
   verify: <verify コマンド>
   ---

   # <repo>

   ## 構成

   （主要なディレクトリと役割）

   ## 検証

   repo 直下で `<verify コマンド>`（verify.py が実行する）。

   ## 現況

   初期状態。
   ```

4. `_harness/context/INDEX.md` の「projects」に1行足す（例: `` - `projects/<repo>.md` — <一言の説明> ``）。
5. Issue をファイルで管理するなら `repos/<repo>/ISSUES.md` に `- #1 [bug] ...` の形で並べると、sessionStart hook が未着手の Issue として表示する。

### 5. 好みを聞く

`_harness/context/PROFILE.md` の既定値（日本語・結論から短く・選択肢で確認・テスト先行）を見せ、変えたい点がないか聞く。言語ごとの書き方の作法があれば `_harness/context/styles/<言語>.md` に書き、INDEX.md に1行足す。

### 6. 検証する

展開先で次を実行し、**両方 exit 0** を確かめる。結果は実際の出力で報告する。

```bash
python3 -m unittest discover -s _harness/tests -t .
python3 _harness/scripts/doctor.py
```

doctor が NG を出したら、`harness-doctor` スキル（`.github/skills/harness-doctor/SKILL.md`）の読み方に従って直す。

### 7. 最初の commit

ハーネス本体（`repos/` 以外）を commit する。push はしない（preToolUse hook も止める）。

```bash
git add -A && git commit -m "chore: add dev-task harness"
```

### 8. 利用者に伝えること

- **VS Code のウィンドウを再読み込み**し、ワークスペースを信頼する。hook・カスタムエージェント・スキルは読み込み時に反映される。
- hook は VS Code ではプレビュー機能。読み込まれたかは、Chat で `/hooks` を入力するか Agent Customizations エディタで確かめる。新しいチャットを開くと、冒頭に「ハーネス: 前回の続き」が出れば sessionStart hook が動いている。
- 使い始めは「repos/<repo> の #1 を直して」のように頼む。以後は `dev-task` スキルの8手順で進む。
- Windows で `python3` がない場合は `.github/hooks/harness.json` の `command` を `python` か `py -3` に変える。
- サブエージェントのモデルを変えたいときは `.github/agents/*.agent.md` に `model:` を足す。

## してはいけないこと

- 既存ファイルの上書き・削除・移動（衝突は利用者に戻す）。
- `git push`。
- 利用者に確認せずに verify コマンドを決めること（推測した案は選択肢で示す）。

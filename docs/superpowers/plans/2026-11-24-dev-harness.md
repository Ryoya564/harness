# 開発タスク・ハーネス Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `~/dev/harness` 内で完結する、Claude Code 用の開発タスク・ハーネス（規約・記録・文脈・検査＋3 hooks＋3 サブエージェント＋doctor）と、それで扱う練習リポジトリ `repos/todo-cli` を作る。

**Architecture:** 入口 `CLAUDE.md` → 正本 `_harness/AGENTS.master.md`。状態はすべて Markdown/JSONL ファイル（task-first）。決定的な処理は `_harness/scripts/*.py`（Python 標準ライブラリのみ）に寄せ、hooks は薄いラッパーにする。完了判定は `close_task.py` が verify コマンドの exit code で行う。

**Tech Stack:** Python 3.12 標準ライブラリ（ハーネス）、unittest（ハーネスのテスト）、Python + pytest + ruff in `.venv`（練習リポジトリ）、git、Claude Code 2.1.x（hooks / agents / skills / settings.json）

**Spec:** `docs/superpowers/specs/2026-11-24-dev-harness-design.md`（各タスクで該当節を参照する）

## Global Constraints

- グローバル設定（`~/.claude/`）には一切書き込まない。すべて `/home/sr_4070/dev/harness` 内。
- ハーネスのコード（`_harness/hooks`, `_harness/scripts`）は Python 標準ライブラリのみ。jq 不使用。
- ハーネスのテストは `python3 -m unittest discover -s _harness/tests -t .` で走る（pytest 非依存）。
- 全スクリプトはハーネスのルートを `lib.harness_root()` で求める: 環境変数 `HARNESS_ROOT` があればそれ、なければ `Path(__file__).resolve().parents[2]`。テストは `HARNESS_ROOT` に一時ディレクトリを渡す。
- ハーネス文書・テンプレート・ユーザー向け出力は日本語。
- タスクID形式 `T-YYYYMMDD-NN`。status は `open | in_progress | done | dropped`、type は `feature | bugfix | refactor | chore`、verify は `pass | fail | none`。
- 文字数上限: PROFILE.md 3000 / context/INDEX.md 3000 / projects/*.md 5000 / styles/*.md 3000 / knowledge/*.md 3000（frontmatter を含む全文字数）。
- 記録ファイルの書き込みは Python で行う（シェルの echo/sed で書かない）。ファイルは UTF-8（BOM なし）、改行 LF。
- hooks はいかなる例外でも exit 0 で通し、エラーは `_harness/state/hook-errors.log` に追記する。
- push・リモート操作は一切しない。

## Review Focus

1. **タイトルに `:` `#` `"` や日本語を含むタスク** → frontmatter が往復で壊れない（Task 2 のテスト `test_roundtrip_special_chars`）。
2. **hook に壊れた／欠けた stdin JSON が来る、cwd がルートでない** → 例外を出さず exit 0、hook-errors.log に記録（Task 5・6 のテスト `test_bad_stdin_passes`）。
3. **active ファイルが指すタスクが存在しない／TASK_ID の打ち間違い** → スクリプトは exit 2 と日本語のエラー1行、トレースバックを出さない（Task 3 のテスト `test_unknown_task_exit2`）。
4. **verify の出力が大量・非 UTF-8** → `errors="replace"` でデコードし、末尾40行だけを log.md に書く（Task 4 のテスト `test_verify_tail_and_binary`）。
5. **close 時に commit する変更がない／ハーネス側が git でない** → close は成功扱いで commit だけ飛ばし、その旨を出力する（Task 4 のテスト `test_close_nothing_to_commit`）。

---

## File Structure

| パス | 責務 |
|---|---|
| `.gitignore` | `repos/`, `_harness/state/`, `__pycache__/` |
| `CLAUDE.md` | `@_harness/AGENTS.master.md` の1行 |
| `.claude/settings.json` | hooks 登録、permissions |
| `.claude/agents/{implementer,reviewer,verifier}.md` | サブエージェント定義 |
| `.claude/skills/dev-task/SKILL.md`, `.claude/skills/harness-doctor/SKILL.md` | 手順 |
| `_harness/AGENTS.master.md`, `_harness/README.md` | 規約正本、設計要約＋採らなかった案 |
| `_harness/context/...` | PROFILE / INDEX / projects/todo-cli.md / styles/python.md / knowledge/.gitkeep |
| `_harness/templates/{TASK,log,DECISIONS}.md` | 雛形 |
| `_harness/scripts/lib.py` | 共通処理（下記 Interfaces） |
| `_harness/scripts/{new_task,set_task,build_index,verify,close_task,doctor}.py` | CLI |
| `_harness/hooks/{session_start,stop_check,session_end}.py` | hooks |
| `_harness/tests/test_*.py`, `_harness/tests/helpers.py` | unittest |
| `repos/todo-cli/` | 練習リポジトリ（独立 git） |

---

### Task 0: ハーネスのリポジトリ初期化

**Files:** Create: `.gitignore`

- [ ] **Step 1:** `git init -b main` を `/home/sr_4070/dev/harness` で実行。
- [ ] **Step 2:** `.gitignore` に `repos/`, `_harness/state/`, `__pycache__/`, `*.pyc` を書く。
- [ ] **Step 3:** Commit: `git add .gitignore docs && git commit -m "docs: add harness design and plan"`
  Expected: `git log --oneline` に1件。

---

### Task 1: 練習リポジトリ repos/todo-cli（Spec §12）

**Files:**
- Create: `repos/todo-cli/{pyproject.toml,README.md,ISSUES.md,.gitignore}`
- Create: `repos/todo-cli/src/todo/{__init__.py,__main__.py,cli.py,store.py,models.py}`
- Create: `repos/todo-cli/tests/{test_store.py,test_cli.py}`

**Interfaces:**
- Produces: verify コマンド `.venv/bin/pytest -q && .venv/bin/ruff check .`（repo 直下で実行）。
- `models.Task`（dataclass: `id: int, title: str, due: date | None, done: bool, created: datetime`）
- `store.load(path: Path) -> list[Task]`, `store.save(path: Path, tasks: list[Task]) -> None`, `store.default_path() -> Path`（`TODO_FILE` 環境変数、なければ `~/.todo-cli.json`）
- `cli.main(argv: list[str] | None = None) -> int`。サブコマンド `add TITLE [--due YYYY-MM-DD]`, `list [--sort due|created]`, `done ID`。

- [ ] **Step 1:** `python3 -m venv .venv && .venv/bin/pip install pytest ruff` を repo 内で実行。pip が使えない場合は止めてユーザーに報告する。
- [ ] **Step 2:** テストを書く: `test_add_and_list`（追加したタイトルが list の出力に出る）、`test_done_marks_task`（`done 1` 後に `[x]` 表示）、`test_sort_due_orders_by_date`（**全タスクに期限あり**のとき昇順）、`test_store_roundtrip`（save→load で同値）。すべて `TODO_FILE` を `tmp_path` に向ける。
- [ ] **Step 3:** 実装する。**仕込みバグ**: `list --sort due` は `sorted(tasks, key=lambda t: t.due)` とする（期限なしが混ざると TypeError）。それ以外は正しく実装する。
- [ ] **Step 4:** `pyproject.toml` に `[tool.ruff] line-length = 100`、`[tool.ruff.lint] select = ["E","F","I"]`、`[tool.pytest.ini_options] pythonpath = ["src"]`。
- [ ] **Step 5:** 実行: `.venv/bin/pytest -q && .venv/bin/ruff check .` → Expected: 全 PASS、ruff `All checks passed!`
- [ ] **Step 6:** バグの再現を確認: 期限あり1件・なし1件を追加して `python -m todo list --sort due` → Expected: `TypeError`。
- [ ] **Step 7:** `ISSUES.md` に Spec §12 の #1〜#4 を、そのままの文言で書く。`README.md` に使い方を書く。`.gitignore` に `.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/` を書く。
- [ ] **Step 8:** `git init -b main && git add -A && git commit -m "initial: todo-cli with seeded issues"`（repos/todo-cli 内で実行）。

---

### Task 2: 共通ライブラリ lib.py

**Files:** Create: `_harness/scripts/lib.py`, `_harness/tests/helpers.py`, `_harness/tests/test_lib.py`, `_harness/tests/__init__.py`, `_harness/scripts/__init__.py`

**Interfaces（Produces。後続の全タスクが使う）:**
- `harness_root() -> Path`
- `now_iso() -> str`。ローカル時刻で、オフセットを含み秒まで（例 `2026-11-24T21:40:00+09:00`）。
- `parse_frontmatter(text: str) -> tuple[dict[str, str | list[str]], str]`、`dump_frontmatter(meta: dict, body: str) -> str`。仕様は次のとおり。
  - `---` で挟んだ `key: value` 行を読む。
  - リストは `[a, b]`。
  - 値に `:#[],"` か先頭・末尾の空白を含むときは、ダブルクォートで囲み `\"` と `\\` をエスケープする。
  - キーの順序を保つ。
  - frontmatter がなければ `({}, text)` を返す。
  - 形式が不正なら `FrontmatterError(ValueError)` を送出する。
- `class HarnessError(Exception)`。CLI はこれを捕まえ、メッセージを stderr に出して exit 2 する。
- `task_dir(task_id: str) -> Path`。`journal/tasks/*/<task_id>` を探す。見つからなければ `HarnessError("タスクが見つかりません: <id>")`。
- `read_task(task_id) -> tuple[dict, str]`、`update_task(task_id, **fields) -> dict`（`touched` も自動更新する）
- `all_tasks() -> list[dict]`。各 meta に `_path` キー（TASK.md の Path）を付ける。frontmatter が壊れたものは飛ばす。
- `append_log(task_id: str, heading: str, body: str) -> None`。追記する形式は `\n## <now_iso()> <heading>\n\n<body>\n`。
- `resolve_session(arg: str | None) -> str | None`。arg がなければ環境変数 `HARNESS_SESSION_ID` を使う。
- `get_active(session_id) -> str | None`、`set_active(session_id, task_id)`、`clear_active(session_id)`。ファイルは `journal/active/<session_id>`。
- `resolve_task(task_id: str | None, session_id: str | None) -> str`。task_id がなければ active を使う。どちらもなければ HarnessError。
- `project_meta(repo: str) -> dict`（`context/projects/<repo>.md` の frontmatter）、`repo_dir(repo) -> Path`
- `run_cli(main_fn) -> NoReturn`。main を実行し、HarnessError なら exit 2 する。
- `helpers.make_root() -> Path`。一時ハーネスを作る。中身は `_harness/{context/projects,journal/tasks,journal/active,templates,state}`、本物の templates のコピー、`repos/demo`（git init 済みで1 commit、verify は `true`）、`context/projects/demo.md`。あわせて `HARNESS_ROOT` を設定する。

- [ ] **Step 1:** テストを書く:
  - `test_roundtrip_special_chars`: タイトル `'修正: "#1" [bug]'` と sessions `["a","b"]` が往復で一致する。
  - `test_no_frontmatter`: frontmatter のない文字列で `({}, text)` が返る。
  - `test_bad_frontmatter_raises`: 閉じ `---` がないと FrontmatterError になる。
  - `test_active_roundtrip`: active の設定・取得・解除ができる。
  - `test_resolve_task_errors`: task_id も active もないと HarnessError になる。
  - `test_append_log_format`: 見出しが `## 2026-` で始まる。
- [ ] **Step 2:** 実行: `python3 -m unittest _harness.tests.test_lib -v` → Expected: FAIL（ImportError）
- [ ] **Step 3:** lib.py と helpers.py を実装する（Interfaces のとおり）。
- [ ] **Step 4:** 再実行 → Expected: PASS
- [ ] **Step 5:** Commit `feat(harness): add lib`

---

### Task 3: テンプレートとタスク操作 new_task / set_task / build_index（Spec §7, §8）

**Files:** Create: `_harness/templates/{TASK,log,DECISIONS}.md`, `_harness/scripts/{new_task,set_task,build_index}.py`, `_harness/tests/test_tasks.py`

**Interfaces:**
- Consumes: Task 2 の lib 全般
- Produces:
  - `new_task.create(title, type_, repo, issue=None, session=None) -> str`（task_id）。CLI は `--title --type --repo [--issue] [--session]` を受け、task_id を stdout に1行で出す。
  - `set_task.assign(task_id, session) -> None`
  - `build_index.write_index() -> Path`、`build_index.render(tasks: list[dict]) -> str`
- TASK.md の初期 frontmatter は Spec §7 のキー順に並べる: `status: in_progress`、`verify: none`、`closed:` は空、`sessions` はセッションがあれば `[id]`、なければ `[]`。
- DECISIONS.md の雛形は表 `| 決定 | 理由 | 却下した案 |` だけ。log.md の雛形は `# <id> log` の1行。
- INDEX.md の形式は次のとおり。
  - 見出しは `# タスク索引（自動生成・手で編集しない）`。
  - 次に `## 未完了` と `## 完了・中止` の2つの表を置き、列は `| ID | タイトル | repo | status | touched |`。
  - 各表は touched の降順に並べる。

- [ ] **Step 1:** テストを書く:
  - `test_new_task_creates_files`: 3ファイルがあり、id が `T-\d{8}-01` で、active が設定され、INDEX に ID がある。
  - `test_new_task_sequence`: 同じ日の2件目が `-02` になる。
  - `test_new_task_unknown_repo_exit2`: repo がないと `SystemExit(2)` になる。
  - `test_set_task_adds_session`: 重複なしでセッションを追加し、status が in_progress になる。
  - `test_unknown_task_exit2`: 存在しない ID で set_task を呼ぶと exit 2 になる。
  - `test_index_sections`: done のタスクは「完了・中止」の表に入る。
- [ ] **Step 2:** 実行して FAIL を確認する。
- [ ] **Step 3:** 実装する。
- [ ] **Step 4:** `python3 -m unittest _harness.tests.test_tasks -v` → PASS
- [ ] **Step 5:** Commit `feat(harness): task scripts and templates`

---

### Task 4: verify / close_task（Spec §8）

**Files:** Create: `_harness/scripts/{verify,close_task}.py`, `_harness/tests/test_close.py`

**Interfaces:**
- Consumes: lib、`build_index.write_index`
- Produces:
  - `verify.run(task_id) -> int`（verify コマンドの終了コード）。処理は次のとおり。
    - `subprocess.run(cmd, shell=True, cwd=repo_dir, capture_output=True)` で実行し、`errors="replace"` でデコードする。
    - log.md に見出し `verify (exit N)` と、```` ``` ```` で囲んだ stdout と stderr の末尾40行を追記する。
    - TASK.md の verify を更新する（0 なら pass、それ以外は fail）。
    - CLI は `verify.py [TASK_ID] [--session]`。
  - `close_task.close(task_id, drop_reason=None) -> int`（0 / 1）。通常の close は次の順に処理する。
    1. verify.run を実行する。0 でなければ 1 を返し、status は変えない。
    2. status=done にし、closed に今日の日付を入れる。
    3. repo で `git add -A && git commit -m "<id>: <title>"` を実行する。変更がなければ commit を飛ばし、その旨を出力する。
    4. active を指しているセッションをすべて解除する。
    5. write_index を実行する。
    6. ハーネス側で、`git rev-parse` が通る場合だけ `git add _harness/journal _harness/context && git commit -m "journal: <id> close"` を実行する。差分がなければ飛ばす。
    7. 結果を log.md に追記する。
  - `--drop` を付けた場合は、手順 1・3 を飛ばして status=dropped にし、理由を log に書く。

- [ ] **Step 1:** テストを書く（helpers.make_root を使い、demo repo の verify を書き換えて使う）:
  - `test_verify_pass_updates_task`: verify が `true` なら TASK.md の verify が pass になり、log に `verify (exit 0)` がある。
  - `test_verify_tail_and_binary`: verify が `python3 -c "import sys;[print(i) for i in range(100)];sys.stdout.buffer.write(b'\xff\n')"` のとき、log に `99` があり、`0\n` だけの行はなく、デコードで例外が出ない。
  - `test_close_fails_when_verify_fails`: verify が `false` なら close は 1 を返し、status は in_progress のまま。
  - `test_close_commits_repo`: repo にファイルを足して close すると、`git log -1 --format=%s` が `<id>: <title>` になる。
  - `test_close_nothing_to_commit`: 変更なしで close しても 0 を返し、status が done になる。
  - `test_drop`: `--drop "不要"` で status が dropped になり、log に `不要` がある。
- [ ] **Step 2:** FAIL を確認 → **Step 3:** 実装 → **Step 4:** `python3 -m unittest _harness.tests.test_close -v` PASS
- [ ] **Step 5:** Commit `feat(harness): verify and close_task`

---

### Task 5: SessionStart / SessionEnd hooks（Spec §10）

**Files:** Create: `_harness/hooks/{session_start,session_end}.py`, `_harness/hooks/_common.py`, `_harness/tests/test_hooks_start_end.py`

**Interfaces:**
- `_common.read_payload() -> dict`（stdin の JSON。読めなければ `{}`）、`_common.safe_main(fn)`（どの例外でも `state/hook-errors.log` に `<now_iso> <hook名> <traceback 最終行>` を追記して exit 0）
- `session_start.build_context(payload: dict, now: float) -> str`。`main` は `{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext": <str>}}` を stdout に出す。`CLAUDE_ENV_FILE` があれば、そのファイルに `export HARNESS_SESSION_ID=<id>\n` を追記する。
- additionalContext に含めるもの（見出しはこの文言で）:
  - `## セッション`：ID と「スクリプトには --session <id> を渡すこと」
  - `## 未完了タスク`：各行は `- <id> <title>（<repo>）次: <log.md の最後に出てくる「次にやること」行。なければ「記録なし」>`
  - `## 未着手の Issue`：`repos/*/ISSUES.md` の `- #` で始まる行のうち、どの TASK.md の issue にも出てこないもの
  - `## doctor`：`state/doctor-last-run` が無いか、7日以上前なら、`doctor.run_checks` を実行して時刻を記録し、NG/WARN の件数と上位5行を載せる。Task 7 の doctor がまだないときは、この節を出さない（ImportError を飲み込む）。
- `session_end.record(payload: dict) -> None`。処理は次のとおり。
  - `journal/sessions.jsonl` を全行読み込み、同じ session_id の行を除いてから `{session_id, transcript_path, ended_at, reason, task_id}` を追記し、書き戻す。
  - active タスクがあれば、`update_task` で touched を更新する。

- [ ] **Step 1:** テストを書く:
  - `test_start_lists_open_tasks_and_issues`: open タスク1件と、未着手 Issue 行が出る。
  - `test_start_writes_env_file`
  - `test_end_dedups_sessions`: 同じ ID で2回呼んでも1行だけ。
  - `test_bad_stdin_passes`: stdin が `"{bad"` でも subprocess の returncode が 0 で、hook-errors.log に記録は出ない。空の payload として正常に処理される。
  - `test_exception_logged`: build_context に例外を注入すると returncode 0 になり、hook-errors.log に1行出る。
- [ ] **Step 2-4:** FAIL を確認 → 実装 → `python3 -m unittest _harness.tests.test_hooks_start_end -v` PASS
- [ ] **Step 5:** Commit `feat(harness): session start/end hooks`

---

### Task 6: Stop hook（Spec §10 Stop）

**Files:** Create: `_harness/hooks/stop_check.py`, `_harness/tests/test_stop.py`

**Interfaces:**
- `stop_check.evaluate(payload: dict, now: float) -> dict | None`。block のときは `{"decision":"block","reason": str}` を返す。`main` はそれを JSON で出力し、None なら何も出さない。どちらの場合も exit 0。
- `edited_repo_paths(transcript_path: str | None) -> set[str]`。transcript の各 JSONL 行から、`message.content[]` のうち `type=="tool_use"` かつ name が `Edit/Write/NotebookEdit` の `input.file_path`（または `notebook_path`）で、`<root>/repos/` 配下のものを集める。読めない場合は空集合を返す。
- `dirty_files(repo: Path) -> list[tuple[str, float]]`。`git status --porcelain` の対象のうち実在するものを、mtime とともに返す。
- 判定の順序:
  1. `stop_hook_active` が真なら None を返す。
  2. active タスクがない場合：「transcript の編集がある」か「`repos/*` のどれかに dirty_files がある」なら、条件 a。
  3. active タスクがある場合：
     - TASK.md の sessions に session_id がなければ、条件 c。
     - その repo の dirty_files の最新 mtime が log.md の mtime より新しく、かつ `now - log_mtime >= 1800` なら、条件 b。
- 指紋: 条件 a・b は `sha256("a|b" + 並べ替えた "path:mtime" の列)`、条件 c は `"c|"+task_id`。`state/stop-blocks.json` の `{session_id: [指紋...]}` に既にあれば、その条件は無視する。残った条件が1つ以上あれば block し、指紋を保存する。
- reason の書式: 1行目は `記録漏れがあります。次を済ませてから終了してください:`、続いて残った条件に対応する行を `- ` で並べる。
  - a: `repos/ を変更していますがタスクが割り当てられていません。new_task.py か set_task.py を実行してください`
  - b: `<task_id> の log.md に、作業内容・判断・次にやることを追記してください（完了なら close_task.py）`
  - c: `set_task.py <task_id> --session <id> でこのセッションを記録してください`

- [ ] **Step 1:** テストを書く（make_root、偽の transcript、`os.utime` で mtime を操作）:
  - `test_active_flag_passes`
  - `test_a_untasked_edit_blocks`
  - `test_a_dirty_repo_without_transcript_blocks`
  - `test_b_blocks_after_30min`
  - `test_b_not_within_30min`
  - `test_c_missing_session_blocks`
  - `test_same_fingerprint_blocks_once`
  - `test_new_change_blocks_again`
  - `test_clean_passes`
  - `test_bad_stdin_passes`
- [ ] **Step 2-4:** FAIL を確認 → 実装 → `python3 -m unittest _harness.tests.test_stop -v` PASS
- [ ] **Step 5:** Commit `feat(harness): stop hook`

---

### Task 7: harness-doctor（Spec §11）

**Files:** Create: `_harness/scripts/doctor.py`, `_harness/tests/test_doctor.py`

**Interfaces:**
- `Finding = namedtuple("Finding", "level what where fix")`。level は `NG|WARN|INFO`。
- `run_checks(root: Path) -> list[Finding]`。Spec §11 の NG・WARN・INFO をすべて実装する。WARN「新しい hook エラー」は、hook-errors.log の行のうち `state/doctor-last-run` より新しいもの。
- `format_report(findings) -> str`。1件ごとに1行 `LEVEL  what  where  fix` を出し、最後に `NG n / WARN n / INFO n` を出す。
- `selftest() -> bool`。一時ディレクトリに4種類の故障を作り、`run_checks` が期待する finding を出すか確かめる。4種類とは、必須キーの欠けた TASK.md、log.md への `\x07` 混入、3001字の PROFILE.md、settings.json から Stop hook を除いたもの。
- CLI は `doctor.py [--selftest] [--quiet]`。NG があれば exit 1。`--quiet` のときは NG と WARN だけを出す。実行時に `state/doctor-last-run` へ時刻を書く。

- [ ] **Step 1:** テストを書く: 各 NG・WARN 項目について、1件ずつ「壊した状態で検出される」テストを書く（`test_ng_*` / `test_warn_*`）。ほかに `test_healthy_root_has_no_ng`（make_root に settings.json と context を足した健全な状態）、`test_selftest_true` を書く。
- [ ] **Step 2-4:** FAIL を確認 → 実装 → `python3 -m unittest _harness.tests.test_doctor -v` PASS
- [ ] **Step 5:** Commit `feat(harness): doctor`

---

### Task 8: 規約・文脈・設定・サブエージェント・スキル（Spec §5, §6, §9, §10 permissions）

**Files:** Create: `CLAUDE.md`, `_harness/AGENTS.master.md`, `_harness/README.md`, `_harness/context/{PROFILE.md,INDEX.md,projects/todo-cli.md,styles/python.md,knowledge/.gitkeep}`, `.claude/settings.json`, `.claude/agents/{implementer,reviewer,verifier}.md`, `.claude/skills/{dev-task,harness-doctor}/SKILL.md`, `_harness/journal/{sessions.jsonl,INDEX.md}`（空・生成）

**Interfaces:**
- `settings.json` の hooks: `SessionStart`、`Stop`、`SessionEnd` の3つ。それぞれ `[{"hooks":[{"type":"command","command":"python3 \"$CLAUDE_PROJECT_DIR/_harness/hooks/<name>.py\""}]}]`。permissions は Spec §10 のとおり（allow は `Bash(python3 _harness/scripts/:*)`, `Bash(python3 _harness/hooks/:*)`, `Bash(.venv/bin/pytest:*)`, `Bash(.venv/bin/ruff:*)`, `Bash(git status:*)`, `Bash(git diff:*)`, `Bash(git log:*)`, `Bash(git add:*)`, `Bash(git commit:*)`。deny は `Bash(git push:*)`, `Bash(rm -rf:*)`）。
- `projects/todo-cli.md` の frontmatter は `repo: todo-cli` と `verify: .venv/bin/pytest -q && .venv/bin/ruff check .`。本文には CLI の構成と ISSUES.md の場所を書く。
- AGENTS.master.md は Spec §6 の11項目を全部含める。冒頭で `@context/PROFILE.md` と `@context/INDEX.md` を取り込む。
- agents の frontmatter は `name`, `description`, `tools`（Spec §9 の表のとおり）, `model: sonnet`。本文に、共通ルール3点（journal と context に書かない／ls で存在を確かめる／決まった見出しで報告）と、各役割の報告書式を書く。
- dev-task スキルは Spec §9 の8手順を、実際のコマンド（`python3 _harness/scripts/new_task.py --title ... --session $HARNESS_SESSION_ID` など）つきで書く。description は1,024字以内。

- [ ] **Step 1:** すべてのファイルを書く。
- [ ] **Step 2:** `python3 _harness/scripts/build_index.py`、続けて `python3 _harness/scripts/doctor.py` → Expected: `NG 0`（exit 0）。
- [ ] **Step 3:** `python3 _harness/scripts/doctor.py --selftest` → exit 0。`python3 -m unittest discover -s _harness/tests -t . -v` → 全 PASS。
- [ ] **Step 4:** settings.json の構文を確かめる: `python3 -c "import json;json.load(open('.claude/settings.json'))"`
- [ ] **Step 5:** Commit `feat(harness): rules, context, agents, skills, settings`

---

### Task 9: 実地確認（使い捨てコピー）（Spec §13-4）

**Files:** なし（scratchpad で作業）

- [ ] **Step 1:** `cp -a /home/sr_4070/dev/harness <scratchpad>/harness-trial` でコピーする（repos/todo-cli と .venv を含む）。コピー先の `.venv` が元のパスを指しているので、コピー先の todo-cli で `python3 -m venv --clear .venv && .venv/bin/pip install pytest ruff` を実行し直す。
- [ ] **Step 2:** コピー先で `cd <copy> && claude -p "ISSUES.md の #1 を dev-task スキルに従って直してください" --permission-mode acceptEdits` を実行する（タイムアウト 10 分）。
- [ ] **Step 3:** 次を確かめる。
  - コピー先の journal/tasks に TASK.md が1件あり、status は done、verify は pass になっている。
  - log.md に verify の記録がある。
  - todo-cli の `git log -1` がタスクIDで始まる。
  - sessions.jsonl に1行ある。
  - `doctor.py` の NG が 0 件。
- [ ] **Step 4:** うまくいかなかった点は、原因を直して本物の `~/dev/harness` に反映し、テストを足してから commit する。本物の journal と todo-cli は初期状態のまま残す。
- [ ] **Step 5:** 本物の側で、unittest 全件、`doctor.py`、`doctor.py --selftest` を最終確認する。結果をユーザーに報告し、対話セッションでの確認手順（`cd ~/dev/harness && claude`、「ISSUES.md の #1 を直して」）を伝える。

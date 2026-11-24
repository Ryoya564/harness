"""harness-doctor: ハーネスの破損を報告する（直さない）。NG があれば exit 1。

clean は「検査範囲の中で異常なし」という意味で、それ以上ではない。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
from collections import Counter, namedtuple
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_index  # noqa: E402
import lib  # noqa: E402

Finding = namedtuple("Finding", "level what where fix")

HOOKS = {"SessionStart": "session_start.py", "Stop": "stop_check.py",
         "SessionEnd": "session_end.py"}
REQUIRED = ("id", "title", "type", "repo", "status", "started")
ALWAYS = {"PROFILE.md": 3000, "INDEX.md": 3000}
ON_DEMAND = {"projects": 5000, "styles": 3000, "knowledge": 3000}
CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f]")
STALE_DAYS = 7
SKILL_DESC_MAX = 1024


def _rel(root: Path, p: Path) -> str:
    try:
        return str(p.relative_to(root))
    except ValueError:
        return str(p)


def _check_hooks(root: Path) -> list[Finding]:
    path = root / ".claude/settings.json"
    if not path.exists():
        return [Finding("NG", "settings.json がない（hooks 未登録）", _rel(root, path),
                        "Spec §10 のとおり settings.json を作る")]
    try:
        hooks = json.loads(path.read_text(encoding="utf-8")).get("hooks", {})
    except json.JSONDecodeError as e:
        return [Finding("NG", f"settings.json が JSON として読めない: {e}", _rel(root, path),
                        "JSON の構文を直す")]
    out = []
    for event, script in HOOKS.items():
        cmds = [h.get("command", "") for grp in hooks.get(event, []) for h in grp.get("hooks", [])]
        if not any(script in c for c in cmds):
            out.append(Finding("NG", f"{event} hook が登録されていない", _rel(root, path),
                               f"{event} に _harness/hooks/{script} を登録する"))
        elif not (root / "_harness/hooks" / script).exists():
            out.append(Finding("NG", f"{event} hook のスクリプトがない",
                               f"_harness/hooks/{script}", "スクリプトを復元する"))
    return out


def _load_tasks(root: Path) -> tuple[list[dict], list[Finding]]:
    tasks, out = [], []
    for p in sorted((root / "_harness/journal/tasks").glob("*/*/TASK.md")):
        try:
            meta, _ = lib.parse_frontmatter(p.read_text(encoding="utf-8"))
        except (lib.FrontmatterError, UnicodeDecodeError) as e:
            out.append(Finding("NG", f"TASK.md の frontmatter が読めない: {e}", _rel(root, p),
                               "frontmatter を手で直す"))
            continue
        missing = [k for k in REQUIRED if not meta.get(k)]
        if missing:
            out.append(Finding("NG", f"TASK.md の必須キーが欠けている: {', '.join(missing)}",
                               _rel(root, p), "欠けたキーを補う"))
            continue
        meta["_path"] = p
        tasks.append(meta)
    return tasks, out


def _check_tasks(root: Path, tasks: list[dict], now: float) -> list[Finding]:
    out = []
    for t in tasks:
        where = _rel(root, t["_path"])
        if t.get("status") == "done" and t.get("verify") != "pass":
            out.append(Finding("NG", f"done なのに verify が pass でない ({t.get('verify')})",
                               where, "verify.py を実行して結果を確認する"))
        if t.get("status") == "in_progress":
            try:
                touched = datetime.fromisoformat(str(t.get("touched"))).timestamp()
            except ValueError:
                touched = 0.0
            if now - touched >= STALE_DAYS * 86400:
                out.append(Finding("WARN", f"in_progress のまま{STALE_DAYS}日以上更新がない",
                                   where, "続けるか close_task.py --drop で中止する"))
    return out


def _check_control_chars(root: Path) -> list[Finding]:
    out = []
    for base in ("_harness/journal", "_harness/context"):
        for p in sorted((root / base).rglob("*")):
            if p.suffix not in (".md", ".jsonl") or not p.is_file():
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            for n, line in enumerate(text.splitlines(), 1):
                if CONTROL.search(line):
                    out.append(Finding("NG", "制御文字が混入している", f"{_rel(root, p)}:{n}",
                                       "該当箇所を Edit ツールで直す（シェルで書かない）"))
                    break
    return out


def _check_limits(root: Path) -> list[Finding]:
    out = []
    ctx = root / "_harness/context"
    for name, limit in ALWAYS.items():
        p = ctx / name
        if p.exists() and (n := len(p.read_text(encoding="utf-8"))) > limit:
            out.append(Finding("NG", f"常に読む層が上限超過 ({n}/{limit}字)", _rel(root, p),
                               "広げずに projects/styles/knowledge へ分割する"))
    for sub, limit in ON_DEMAND.items():
        for p in sorted((ctx / sub).glob("*.md")):
            if (n := len(p.read_text(encoding="utf-8"))) > limit:
                out.append(Finding("WARN", f"文脈ファイルが上限超過 ({n}/{limit}字)",
                                   _rel(root, p), "テーマごとにファイルを分割する"))
    return out


def _check_projects(root: Path) -> list[Finding]:
    out = []
    for p in sorted((root / "_harness/context/projects").glob("*.md")):
        try:
            meta, _ = lib.parse_frontmatter(p.read_text(encoding="utf-8"))
        except lib.FrontmatterError as e:
            out.append(Finding("NG", f"projects の frontmatter が読めない: {e}", _rel(root, p),
                               "frontmatter を直す"))
            continue
        if not meta.get("verify"):
            out.append(Finding("NG", "projects に verify: がない", _rel(root, p),
                               "完了判定のコマンドを verify: に書く"))
        repo = str(meta.get("repo") or p.stem)
        if not (root / "repos" / repo).is_dir():
            out.append(Finding("NG", f"repo ディレクトリがない: repos/{repo}", _rel(root, p),
                               "repo を置くか projects ファイルを消す"))
    return out


def _check_index(root: Path, tasks: list[dict]) -> list[Finding]:
    p = root / "_harness/journal/INDEX.md"
    if not tasks and not p.exists():
        return []
    current = p.read_text(encoding="utf-8") if p.exists() else ""
    if current != build_index.render(tasks):
        return [Finding("WARN", "journal/INDEX.md が TASK.md の実態と食い違う", _rel(root, p),
                        "build_index.py を実行する")]
    return []


def _check_sessions(root: Path, tasks: list[dict]) -> list[Finding]:
    p = root / "_harness/journal/sessions.jsonl"
    if not p.exists():
        return []
    known = {s for t in tasks for s in (t.get("sessions") or [])}
    orphans = []
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            sid = json.loads(line).get("session_id")
        except (json.JSONDecodeError, AttributeError):
            continue
        if sid and sid not in known:
            orphans.append(sid)
    if orphans:
        return [Finding("WARN", f"どのタスクにも属さないセッションが {len(orphans)} 件",
                        _rel(root, p), "タスクなしで repos/ を触っていないか確認する")]
    return []


def _check_skills(root: Path) -> list[Finding]:
    out = []
    for p in sorted((root / ".claude/skills").glob("*/SKILL.md")):
        try:
            meta, _ = lib.parse_frontmatter(p.read_text(encoding="utf-8"))
        except lib.FrontmatterError:
            meta = {}
        if len(str(meta.get("description", ""))) > SKILL_DESC_MAX:
            out.append(Finding("WARN", f"スキルの description が {SKILL_DESC_MAX} 字超",
                               _rel(root, p), "短くする（超えると無視されることがある）"))
    return out


def _last_run(root: Path) -> float:
    p = root / "_harness/state/doctor-last-run"
    try:
        return float(p.read_text().strip()) if p.exists() else 0.0
    except ValueError:
        return 0.0


def _check_hook_errors(root: Path) -> list[Finding]:
    p = root / "_harness/state/hook-errors.log"
    if not p.exists():
        return []
    since = _last_run(root)
    n = 0
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            if datetime.fromisoformat(line.split(" ", 1)[0]).timestamp() > since:
                n += 1
        except ValueError:
            continue
    if n:
        return [Finding("WARN", f"前回の doctor 以降に hook のエラーが {n} 件", _rel(root, p),
                        "ログを読んで原因を直す")]
    return []


def run_checks(root: Path, now: float | None = None) -> list[Finding]:
    now = time.time() if now is None else now
    tasks, out = _load_tasks(root)
    out += _check_hooks(root)
    out += _check_tasks(root, tasks, now)
    out += _check_control_chars(root)
    out += _check_limits(root)
    out += _check_projects(root)
    out += _check_index(root, tasks)
    out += _check_sessions(root, tasks)
    out += _check_skills(root)
    out += _check_hook_errors(root)
    counts = Counter(str(t.get("status")) for t in tasks)
    summary = ", ".join(f"{k} {v}" for k, v in sorted(counts.items())) or "0件"
    out.append(Finding("INFO", f"タスク: {summary}", "_harness/journal", "-"))
    last = _last_run(root)
    out.append(Finding("INFO", "前回の doctor 実行: " + (
        datetime.fromtimestamp(last).astimezone().isoformat(timespec="seconds") if last
        else "なし"), "_harness/state/doctor-last-run", "-"))
    order = {"NG": 0, "WARN": 1, "INFO": 2}
    return sorted(out, key=lambda f: order[f.level])


def format_line(f: Finding) -> str:
    return f"{f.level}  {f.what}  {f.where}  {f.fix}"


def format_report(findings: list[Finding]) -> str:
    c = Counter(f.level for f in findings)
    lines = [format_line(f) for f in findings]
    lines.append(f"NG {c['NG']} / WARN {c['WARN']} / INFO {c['INFO']}")
    return "\n".join(lines) + "\n"


def mark_run(now: float) -> None:
    lib.write_text(lib.state_dir() / "doctor-last-run", f"{now}\n")


# ---------------------------------------------------------------- selftest

def build_healthy_fixture(root: Path) -> None:
    """root に doctor が NG/WARN を出さない最小構成を足す（テストと selftest 用）。"""
    hooks = {ev: [{"hooks": [{"type": "command",
                              "command": f'python3 "$CLAUDE_PROJECT_DIR/_harness/hooks/{s}"'}]}]
             for ev, s in HOOKS.items()}
    lib.write_text(root / ".claude/settings.json", json.dumps({"hooks": hooks}, indent=2))
    for s in HOOKS.values():
        lib.write_text(root / "_harness/hooks" / s, "")
    lib.write_text(root / "_harness/context/PROFILE.md", "# PROFILE\n")
    lib.write_text(root / "_harness/context/INDEX.md", "# 文脈 INDEX\n")
    lib.write_text(root / "_harness/journal/INDEX.md", build_index.render([]))


def selftest() -> bool:
    """わざと4種類の故障を作り、doctor が検出することを確かめる。"""
    saved = os.environ.get("HARNESS_ROOT")
    tmp = Path(tempfile.mkdtemp(prefix="doctor-selftest-"))
    try:
        os.environ["HARNESS_ROOT"] = str(tmp)
        for d in ("context/projects", "journal/tasks/2026/T-20260101-01", "state"):
            (tmp / "_harness" / d).mkdir(parents=True, exist_ok=True)
        build_healthy_fixture(tmp)
        healthy = [f for f in run_checks(tmp) if f.level != "INFO"]
        if healthy:
            print("selftest: 健全な構成で NG/WARN が出た:\n" + format_report(healthy))
            return False
        task = tmp / "_harness/journal/tasks/2026/T-20260101-01"
        lib.write_text(task / "TASK.md", "---\nid: T-20260101-01\ntitle: x\n---\n")
        lib.write_text(task / "log.md", "bell \x07\n")
        lib.write_text(tmp / "_harness/context/PROFILE.md", "あ" * 3001)
        s = json.loads((tmp / ".claude/settings.json").read_text())
        del s["hooks"]["Stop"]
        lib.write_text(tmp / ".claude/settings.json", json.dumps(s))
        whats = [f.what for f in run_checks(tmp) if f.level == "NG"]
        expect = {"必須キー": "TASK.md 必須キー欠損", "制御文字": "制御文字",
                  "上限": "PROFILE 上限超過", "Stop hook": "Stop hook 未登録"}
        ok = True
        for word, label in expect.items():
            hit = any(word in w for w in whats)
            print(f"selftest: {label}: {'検出' if hit else '未検出'}")
            ok &= hit
        return ok
    finally:
        if saved is None:
            os.environ.pop("HARNESS_ROOT", None)
        else:
            os.environ["HARNESS_ROOT"] = saved


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--quiet", action="store_true", help="NG と WARN だけ出す")
    a = ap.parse_args(argv)
    if a.selftest:
        return 0 if selftest() else 1
    root = lib.harness_root()
    findings = run_checks(root)
    shown = [f for f in findings if f.level != "INFO"] if a.quiet else findings
    print(format_report(shown), end="")
    mark_run(time.time())
    return 1 if any(f.level == "NG" for f in findings) else 0


if __name__ == "__main__":
    lib.run_cli(main)

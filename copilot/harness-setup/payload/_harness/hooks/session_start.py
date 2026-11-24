"""sessionStart: 常に読む文脈・前回の続き・未着手 Issue・doctor の要約を渡す。止めない。

Copilot は指示ファイルの @ 参照をたどらないため、PROFILE.md と context/INDEX.md の本文も
ここで渡す。出力は Copilot が読むトップレベルの additionalContext だけ。
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common  # noqa: E402
import stop_check  # noqa: E402
from _common import lib  # noqa: E402

DOCTOR_INTERVAL = 7 * 24 * 3600
NEXT_RE = re.compile(r"次にやること\s*[:：]\s*(.+)")


def _next_step(task: dict) -> str:
    log = Path(task["_path"]).with_name("log.md")
    found = "記録なし"
    if log.exists():
        for line in lib.read_text(log).splitlines():
            m = NEXT_RE.search(line)
            if m:
                found = m.group(1).strip()
    return found


def _untasked_issues(tasks: list[dict]) -> list[str]:
    taken = {(t.get("repo"), t.get("issue")) for t in tasks if t.get("issue")}
    out = []
    for issues in sorted((lib.harness_root() / "repos").glob("*/ISSUES.md")):
        repo = issues.parent.name
        for line in lib.read_text(issues).splitlines():
            m = re.match(r"-\s*(#\d+)", line)
            if m and (repo, m.group(1)) not in taken:
                out.append(f"- [{repo}] {line[1:].strip()}")
    return out


def _doctor_section(now: float) -> str:
    stamp = lib.state_dir() / "doctor-last-run"
    try:
        last = float(lib.read_text(stamp).strip()) if stamp.exists() else 0.0
    except ValueError:
        last = 0.0
    if now - last < DOCTOR_INTERVAL:
        return ""
    try:
        import doctor  # noqa: PLC0415
    except ImportError:
        return ""
    findings = doctor.run_checks(lib.harness_root())
    doctor.mark_run(now)
    bad = [f for f in findings if f.level in ("NG", "WARN")]
    ng = sum(f.level == "NG" for f in findings)
    lines = [f"NG {ng} / WARN {len(bad) - ng}（週次の自動実行）"]
    lines += [doctor.format_line(f) for f in bad[:5]]
    return "## doctor\n\n" + "\n".join(lines)


ALWAYS_READ = ("PROFILE.md", "INDEX.md")


def _always_read_section() -> str:
    ctx = lib.hdir() / "context"
    bodies = [lib.read_text(ctx / n).strip() for n in ALWAYS_READ if (ctx / n).exists()]
    return "## 常に読む文脈（_harness/context/）\n\n" + "\n\n".join(bodies) if bodies else ""


def build_context(payload: dict, now: float) -> str:
    payload = _common.normalize(payload)
    sid = payload.get("session_id") or "不明"
    if payload.get("session_id") and re.fullmatch(r"[A-Za-z0-9._-]+", sid):
        stop_check.mark_session_start(sid, now)
    tasks = lib.all_tasks()
    open_tasks = [t for t in tasks if t.get("status") in ("open", "in_progress")]
    parts = [
        "## セッション\n\n"
        f"セッションID: {sid}\n"
        f"ハーネスのスクリプトには必ず --session {sid} を渡すこと。",
        "## 未完了タスク\n\n" + ("\n".join(
            f"- {t['id']} {t.get('title', '')}（{t.get('repo', '')}）次: {_next_step(t)}"
            for t in open_tasks) or "なし"),
        "## 未着手の Issue\n\n" + ("\n".join(_untasked_issues(tasks)) or "なし"),
    ]
    always = _always_read_section()
    if always:
        parts.insert(0, always)
    doc = _doctor_section(now)
    if doc:
        parts.append(doc)
    return "# ハーネス: 前回の続き\n\n" + "\n\n".join(parts)


def main() -> None:
    payload = _common.read_payload()
    print(json.dumps({"additionalContext": build_context(payload, time.time())},
                     ensure_ascii=False))


if __name__ == "__main__":
    _common.safe_main("session_start", main)

"""hooks 共通処理。どんな例外でも exit 0 で通し、エラーを state/hook-errors.log に残す。"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path
from typing import Callable, NoReturn

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import lib  # noqa: E402


def read_payload() -> dict:
    try:
        data = json.loads(sys.stdin.read() or "{}")
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


def log_error(hook: str, exc: BaseException) -> None:
    last = traceback.format_exception_only(type(exc), exc)[-1].strip()
    try:
        with open(lib.state_dir() / "hook-errors.log", "a", encoding="utf-8") as f:
            f.write(f"{lib.now_iso()} {hook} {last}\n")
    except OSError:
        pass


def safe_main(hook: str, fn: Callable[[], None]) -> NoReturn:
    try:
        fn()
    except Exception as e:  # noqa: BLE001  hook は決して作業を止めない
        log_error(hook, e)
    sys.exit(0)

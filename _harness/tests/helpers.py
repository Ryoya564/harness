"""テスト用の一時ハーネスを作る。"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REAL_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REAL_ROOT / "_harness" / "scripts"
HOOKS = REAL_ROOT / "_harness" / "hooks"
for p in (str(SCRIPTS), str(HOOKS)):
    if p not in sys.path:
        sys.path.insert(0, p)


def git(repo: Path, *args: str) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True,
                          text=True, env=env).stdout


def make_root(verify: str = "true") -> Path:
    """一時ハーネスを作り HARNESS_ROOT を設定して返す。"""
    root = Path(tempfile.mkdtemp(prefix="harness-test-"))
    h = root / "_harness"
    for d in ("context/projects", "context/styles", "context/knowledge", "journal/tasks",
              "journal/active", "templates", "state"):
        (h / d).mkdir(parents=True, exist_ok=True)
    real_templates = REAL_ROOT / "_harness" / "templates"
    if real_templates.is_dir():
        shutil.copytree(real_templates, h / "templates", dirs_exist_ok=True)
    (h / "context" / "projects" / "demo.md").write_text(
        f"---\nrepo: demo\nverify: {verify}\n---\n\n# demo\n", encoding="utf-8")
    repo = root / "repos" / "demo"
    repo.mkdir(parents=True)
    git(repo, "init", "-q", "-b", "main")
    (repo / "README.md").write_text("demo\n", encoding="utf-8")
    (repo / "ISSUES.md").write_text("# ISSUES\n\n- #1 [bug] demo bug\n- #2 [feature] demo feat\n",
                                    encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "init")
    os.environ["HARNESS_ROOT"] = str(root)
    os.environ.pop("HARNESS_SESSION_ID", None)
    return root


def set_verify(root: Path, verify: str) -> None:
    (root / "_harness/context/projects/demo.md").write_text(
        f"---\nrepo: demo\nverify: {verify}\n---\n\n# demo\n", encoding="utf-8")

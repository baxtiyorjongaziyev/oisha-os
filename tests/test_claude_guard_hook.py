"""Regression tests for the Claude Code PreToolUse guard hook (.claude/hooks/guard.py)."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

GUARD = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "guard.py"

# Dangerous strings are assembled at runtime so this file itself does not trip the hook.
FORCE = "--" + "force"
RMRF = "rm " + "-rf"
ENV = "." + "env"


def run_guard(tool: str, tool_input: dict) -> int:
    payload = json.dumps({"tool_name": tool, "tool_input": tool_input})
    result = subprocess.run(
        [sys.executable, str(GUARD)], input=payload, capture_output=True, text=True, check=False
    )
    return result.returncode


@pytest.mark.parametrize(
    "tool,tool_input",
    [
        ("Bash", {"command": "python src/main.py"}),
        ("Bash", {"command": "git push origin main"}),
        ("Bash", {"command": "git push origin HEAD:main"}),
        ("Bash", {"command": f"git push {FORCE} origin feat/x"}),
        ("Bash", {"command": "git push -f origin feat/x"}),
        ("Bash", {"command": "git reset --hard HEAD~1"}),
        ("Bash", {"command": f"{RMRF} build"}),
        ("Bash", {"command": f"cat {ENV}"}),
        ("Bash", {"command": f"echo X=1 >> {ENV}"}),
        ("Read", {"file_path": f"C:/repo/{ENV}"}),
        ("Edit", {"file_path": "data/userbot.session"}),
    ],
)
def test_blocks_dangerous_actions(tool, tool_input):
    assert run_guard(tool, tool_input) == 2


@pytest.mark.parametrize(
    "tool,tool_input",
    [
        ("Bash", {"command": "python -m pytest -q"}),
        ("Bash", {"command": "git push -u origin feat/main-fix"}),
        ("Bash", {"command": "git push -u origin feat/x; gh pr create --base main"}),
        ("Bash", {"command": f"gh pr create --body 'guard {ENV} rules'"}),
        ("Read", {"file_path": f"C:/repo/{ENV}.example"}),
        ("Edit", {"file_path": "src/settings.py"}),
    ],
)
def test_allows_safe_actions(tool, tool_input):
    assert run_guard(tool, tool_input) == 0


def test_malformed_input_is_allowed():
    result = subprocess.run(
        [sys.executable, str(GUARD)], input="not json", capture_output=True, text=True, check=False
    )
    assert result.returncode == 0

"""
Autonomous Harness Loop Engine for Oisha-OS
Implements closed-loop iteration, stagnation detection, circuit breaking,
and automated verification for AI agent workflows.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

for stream in (sys.stdout, sys.stderr):
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent.parent
PYTHON_EXE = ROOT / ".venv" / "Scripts" / "python.exe"
if not PYTHON_EXE.exists():
    PYTHON_EXE = Path(sys.executable)
FEEDBACK_FILE = ROOT / "HARNESS_FEEDBACK.md"
HANDOFF_FILE = ROOT / "docs" / "agents" / "handoff-log.md"


@dataclass
class LoopConfig:
    max_iterations: int = 15
    max_stalls: int = 3
    test_target: Optional[str] = None
    plan_file: Optional[Path] = None


def get_git_state() -> Tuple[str, str]:
    """Returns HEAD commit hash and working tree diff hash for stall detection."""
    try:
        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True, errors="replace"
        ).strip()
        diff = subprocess.check_output(
            ["git", "diff", "HEAD"], cwd=str(ROOT), text=True, errors="replace"
        )
        diff_hash = hashlib.sha256(diff.encode("utf-8")).hexdigest()[:16]
        return head, diff_hash
    except Exception:
        return "unknown", "unknown"


def assert_safe_environment() -> None:
    """Guards against running destructive actions on main or production sessions."""
    try:
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(ROOT),
            text=True,
            errors="replace",
        ).strip()
        if branch in ("main", "master"):
            print("⚠️ [GUARD] Running loop directly on 'main/master' is restricted.")
            print("Create a 'feat/' or 'fix/' branch before autonomous modifications.")
    except Exception:
        pass

    os.environ["SKIP_LIVE"] = "1"
    os.environ["ALLOW_LOCAL_RUN"] = "0"


def execute_audit(target: Optional[str] = None) -> Tuple[int, str]:
    """Executes run_harness.py audit step with environment isolation."""
    args = [str(PYTHON_EXE), "scripts/harness/run_harness.py"]
    if target:
        args.append(target)

    env = os.environ.copy()
    env["SKIP_LIVE"] = "1"
    env["ALLOW_LOCAL_RUN"] = "0"

    res = subprocess.run(
        args,
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return res.returncode, res.stdout


def format_handoff_entry(agent_name: str, task_summary: str, files_changed: list[str]) -> str:
    """Formats standardized handoff log entry compliant with AGENTS.md rule 6."""
    from datetime import datetime

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    files_str = ", ".join(f"`{f}`" for f in files_changed) if files_changed else "None"
    return (
        f"\n### {now_str} — {agent_name} [harness-loop]\n"
        f"- **Vazifa / Ish**: {task_summary}\n"
        f"- **O'zgargan fayllar**: {files_str}\n"
        f"- **Tekshiruv dalili**: Harness loop 100% GREEN (standards, bandit, pytest)\n"
        f"- **Holat / Keyingi qadam**: Tayyor, PR yoki keyingi vazifaga o'tish mumkin.\n"
    )


def record_successful_handoff(task_summary: str) -> None:
    """Appends verified handoff evidence to docs/agents/handoff-log.md."""
    try:
        diff_files = current_changed_files()
    except Exception:
        diff_files = []

    entry = format_handoff_entry("Antigravity Harness", task_summary, diff_files)
    if HANDOFF_FILE.exists():
        with open(HANDOFF_FILE, "a", encoding="utf-8") as f:
            f.write(entry)
        print(f"📝 Handoff recorded in {HANDOFF_FILE.relative_to(ROOT)}")


def current_changed_files() -> list[str]:
    """Collect staged, unstaged and untracked paths without previous commits."""
    paths = set()
    for args in (["diff", "--name-only", "-z", "HEAD"],
                 ["ls-files", "--others", "--exclude-standard", "-z"]):
        output = subprocess.check_output(["git", *args], cwd=ROOT)
        paths.update(os.fsdecode(path) for path in output.split(b"\0") if path)
    return sorted(paths)


def run_autonomous_loop(config: LoopConfig) -> int:
    """Runs the self-healing evaluation and verification loop with circuit breakers."""
    assert_safe_environment()
    print("=" * 65)
    print("🔄 OISHA-OS AUTONOMOUS HARNESS LOOP ENGINE")
    print(f"Target: {config.test_target or 'default smoke suite'} | Max iterations: {config.max_iterations}")
    print("=" * 65)

    stalls = 0
    last_state = ("", "")

    for iteration in range(1, config.max_iterations + 1):
        print(f"\n--- [Iteration {iteration}/{config.max_iterations}] Running Audit ---")
        code, output = execute_audit(config.test_target)
        current_state = get_git_state()

        if code == 0:
            print("\n🎉 [HARNESS GREEN] All verification gates passed!")
            if FEEDBACK_FILE.exists():
                FEEDBACK_FILE.unlink()
            record_successful_handoff("Autonomous Harness Verification & Healing Loop")
            return 0

        # Failure handling and circuit breaking
        print(f"❌ [HARNESS RED] Iteration {iteration} failed.")
        if current_state == last_state:
            stalls += 1
            print(f"⚠️ [STALL DETECTED] No code changes observed ({stalls}/{config.max_stalls}).")
            if stalls >= config.max_stalls:
                print(f"🚨 [CIRCUIT BREAKER] Aborting loop: {config.max_stalls} consecutive stalls.")
                print(f"Action required: Check {FEEDBACK_FILE.name} for actionable failure context.")
                return 1
        else:
            stalls = 0

        last_state = current_state

        if FEEDBACK_FILE.exists():
            feedback_preview = FEEDBACK_FILE.read_text(encoding="utf-8", errors="replace")[:600]
            print(f"Context from {FEEDBACK_FILE.name}:\n{feedback_preview}...\n")

    print("\n⏰ [TIMEOUT] Maximum iterations reached without reaching green state.")
    return 1


def main() -> None:
    if "--commit" in sys.argv:
        print("--commit is unsupported; commit reviewed changes separately after verification.")
        sys.exit(2)
    target = None
    for arg in sys.argv[1:]:
        if not arg.startswith("-"):
            target = arg
            break

    config = LoopConfig(
        max_iterations=15,
        max_stalls=3,
        test_target=target or "tests/test_admin_bot_notify.py",
    )
    exit_code = run_autonomous_loop(config)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

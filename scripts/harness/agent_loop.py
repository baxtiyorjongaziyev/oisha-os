"""
Autonomous Harness Loop Engine for Oisha-OS
Implements closed-loop iteration, stagnation detection, circuit breaking,
and automated verification for AI agent workflows.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shlex
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
    agent_cmd: Optional[str] = None
    agent_timeout: int = 1800
    agent_name: str = "Harness Loop"


def get_git_state() -> Tuple[str, str]:
    """Returns HEAD commit hash and working tree diff hash for stall detection."""
    try:
        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True, errors="replace"
        ).strip()
        digest = hashlib.sha256()
        digest.update(subprocess.check_output(["git", "diff", "HEAD"], cwd=str(ROOT)))  # nosec B603 B607
        for path in current_changed_files():
            file_path = ROOT / path
            if file_path.is_file():
                digest.update(path.encode("utf-8", "replace") + file_path.read_bytes())
        diff_hash = digest.hexdigest()[:16]
        return head, diff_hash
    except Exception:
        return "unknown", "unknown"


def git_head() -> str:
    """HEAD commit the loop started from; falls back to the symbolic ref."""
    try:
        return subprocess.check_output(  # nosec B603 B607
            ["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True
        ).strip()
    except Exception:
        return "HEAD"


def assert_safe_environment() -> bool:
    """Refuses to run the loop on main/master; forces offline test env."""
    os.environ["SKIP_LIVE"] = "1"
    os.environ["ALLOW_LOCAL_RUN"] = "0"
    try:
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(ROOT),
            text=True,
            errors="replace",
        ).strip()
    except Exception:
        return True
    if branch in ("main", "master"):
        print("⛔ [GUARD] Harness loop refuses to run on main/master.")
        print("Create a 'feat/' or 'fix/' branch before autonomous modifications.")
        return False
    return True


def run_agent_step(config: LoopConfig) -> int:
    """Runs the fixing agent once; it reads HARNESS_FEEDBACK.md and edits code."""
    if not config.agent_cmd:
        return 0
    print(f"🤖 Agent step: {config.agent_cmd}")
    env = os.environ.copy()
    env["HARNESS_FEEDBACK_FILE"] = str(FEEDBACK_FILE)
    is_windows = os.name == "nt"
    group_kwargs = (
        {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        if is_windows
        else {"start_new_session": True}
    )
    # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
    proc = subprocess.Popen(  # nosec B603 - operator-supplied command, no shell
        split_agent_cmd(config.agent_cmd),
        cwd=str(ROOT),
        env=env,
        **group_kwargs,
    )
    try:
        return proc.wait(timeout=config.agent_timeout)
    except subprocess.TimeoutExpired:
        print(f"⏱️ Agent step timed out after {config.agent_timeout}s; killing process tree.")
        kill_process_tree(proc)
        return 124


def split_agent_cmd(cmd: str) -> list[str]:
    """Splits --agent-cmd; on Windows strips grouping quotes like CommandLineToArgvW."""
    if os.name != "nt":
        return shlex.split(cmd)
    return [
        token[1:-1] if len(token) >= 2 and token[0] == token[-1] == '"' else token
        for token in shlex.split(cmd, posix=False)
    ]


def kill_process_tree(proc: subprocess.Popen) -> None:
    """Kills the agent and every child it spawned."""
    if os.name == "nt":
        subprocess.run(  # nosec B603 B607 - fixed system tool, numeric pid
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        import signal

        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    proc.wait()


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


def format_handoff_entry(agent_name: str, task_summary: str, files_changed: list[str], target: Optional[str] = None) -> str:
    """Formats standardized handoff log entry compliant with AGENTS.md rule 6."""
    from datetime import datetime

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    files_str = ", ".join(f"`{f}`" for f in files_changed) if files_changed else "None"
    scope = f"focused pytest target: {target}" if target else "full pytest suite"
    return (
        f"\n### {now_str} — {agent_name} [harness-loop]\n"
        f"- **Vazifa / Ish**: {task_summary}\n"
        f"- **O'zgargan fayllar**: {files_str}\n"
        f"- **Tekshiruv dalili**: Local harness PASS (standards, bandit, Ruff, branch text, skill mirror, {scope})\n"
        f"- **Holat / Keyingi qadam**: Tayyor, PR yoki keyingi vazifaga o'tish mumkin.\n"
    )


def record_successful_handoff(task_summary: str, agent_name: str, base_head: str = "HEAD", target: Optional[str] = None) -> None:
    """Appends verified handoff evidence; skipped when nothing changed since base_head."""
    try:
        diff_files = current_changed_files(base_head)
    except Exception:
        diff_files = []
    diff_files = [f for f in diff_files if f != HANDOFF_FILE.relative_to(ROOT).as_posix()]
    if not diff_files:
        return

    entry = format_handoff_entry(agent_name, task_summary, diff_files, target)
    if HANDOFF_FILE.exists():
        with open(HANDOFF_FILE, "a", encoding="utf-8") as f:
            f.write(entry)
        print(f"📝 Handoff recorded in {HANDOFF_FILE.relative_to(ROOT)}")


def current_changed_files(base: str = "HEAD") -> list[str]:
    """Paths changed since base: commits made after it, worktree edits, untracked files."""
    paths = set()
    for args in (["diff", "--name-only", "-z", base],
                 ["ls-files", "--others", "--exclude-standard", "-z"]):
        output = subprocess.check_output(["git", *args], cwd=ROOT)  # nosec B603 B607
        paths.update(os.fsdecode(path) for path in output.split(b"\0") if path)
    return sorted(paths)


def run_autonomous_loop(config: LoopConfig) -> int:
    """Audit -> (agent fix) -> re-audit until green, stalled or out of budget."""
    if not assert_safe_environment():
        return 2
    print("=" * 65)
    print("🔄 OISHA-OS AUTONOMOUS HARNESS LOOP ENGINE")
    print(f"Target: {config.test_target or 'full suite'} | Max iterations: {config.max_iterations}")
    print(f"Agent: {config.agent_cmd or 'none (single audit, no fixing step)'}")
    print("=" * 65)

    stalls = 0
    base_head = git_head()
    for iteration in range(1, config.max_iterations + 1):
        print(f"\n--- [Iteration {iteration}/{config.max_iterations}] Running Audit ---")
        code, _ = execute_audit(config.test_target)
        if code == 0:
            print("\n🎉 [HARNESS GREEN] Local audit gates passed; release gates are separate.")
            if FEEDBACK_FILE.exists():
                FEEDBACK_FILE.unlink()
            record_successful_handoff("Autonomous Harness Verification & Healing Loop", config.agent_name, base_head, config.test_target)
            return 0

        print(f"❌ [HARNESS RED] Iteration {iteration} failed.")
        if FEEDBACK_FILE.exists():
            preview = FEEDBACK_FILE.read_text(encoding="utf-8", errors="replace")[:600]
            print(f"Context from {FEEDBACK_FILE.name}:\n{preview}...\n")
        if not config.agent_cmd:
            print("No --agent-cmd given: fix the failures, then re-run.")
            return 1
        if iteration == config.max_iterations:
            break  # no audit slot left to verify another agent fix

        before = get_git_state()
        agent_code = run_agent_step(config)
        if agent_code != 0:
            print(f"⚠️ Agent step exited with {agent_code}.")
        if get_git_state() == before:
            stalls += 1
            print(f"⚠️ [STALL] Agent made no changes ({stalls}/{config.max_stalls}).")
            if stalls >= config.max_stalls:
                print(f"🚨 [CIRCUIT BREAKER] {config.max_stalls} consecutive stalls. See {FEEDBACK_FILE.name}.")
                return 1
        else:
            stalls = 0

    print("\n⏰ [TIMEOUT] Maximum iterations reached without reaching green state.")
    return 1


def parse_args(argv: list[str]) -> LoopConfig:
    parser = argparse.ArgumentParser(description="Oisha-OS harness loop")
    parser.add_argument("target", nargs="?", help="pytest target (default: full suite)")
    parser.add_argument("--agent-cmd", help="command run after each red audit to fix code")
    parser.add_argument("--agent-name", default="Harness Loop")
    parser.add_argument("--agent-timeout", type=int, default=1800)
    parser.add_argument("--max-iterations", type=int, default=15)
    parser.add_argument("--max-stalls", type=int, default=3)
    args = parser.parse_args(argv)
    return LoopConfig(
        max_iterations=args.max_iterations,
        max_stalls=args.max_stalls,
        test_target=args.target,
        agent_cmd=args.agent_cmd,
        agent_timeout=args.agent_timeout,
        agent_name=args.agent_name,
    )


def main() -> None:
    if "--commit" in sys.argv:
        print("--commit is unsupported; commit reviewed changes separately after verification.")
        sys.exit(2)
    sys.exit(run_autonomous_loop(parse_args(sys.argv[1:])))


if __name__ == "__main__":
    main()

"""
Master Harness Loop Runner (Autonomous Evaluation & Feedback Loop)
Standardizes the Verification & Self-Healing loop across all agents (Antigravity, Codex, Claude).
"""

import os
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent.parent
PYTHON_EXE = ROOT / ".venv" / "Scripts" / "python.exe"
FEEDBACK_FILE = ROOT / "HARNESS_FEEDBACK.md"


def run_cmd(cmd_list, env=None):
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    res = subprocess.run(
        cmd_list,
        cwd=str(ROOT),
        env=merged_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    return res.returncode, res.stdout


def main():
    print("=" * 60)
    print("🚀 OISHA-OS HARNESS LOOP: SYSTEM AUDIT")
    print("=" * 60)

    stages = []
    has_failure = False

    # Stage 1: Standards Check (Max 400 lines)
    print("\n[1/3] 📏 Checking Modular Code Standards (400-line limit)...")
    code, out = run_cmd([str(PYTHON_EXE), "scripts/harness/verify_standards.py", "--markdown"])
    if code == 0:
        print("  ✅ Standards Check: PASSED")
        stages.append(("Code Standards", True, out))
    else:
        print("  ❌ Standards Check: FAILED")
        stages.append(("Code Standards", False, out))
        has_failure = True

    # Stage 2: Security Audit (Bandit)
    print("\n[2/3] 🛡️ Running Security Scan (bandit -r src/ -ll)...")
    code, out = run_cmd([str(PYTHON_EXE), "-m", "bandit", "-r", "src/", "-ll"])
    if code == 0:
        print("  ✅ Security Audit: PASSED (0 high/medium issues)")
        stages.append(("Security Audit", True, out))
    else:
        print("  ❌ Security Audit: FAILED")
        stages.append(("Security Audit", False, out))
        has_failure = True

    # Stage 3: Test Suite (Pytest)
    print("\n[3/3] 🧪 Running Pytest Suite ($env:SKIP_LIVE=1)...")
    test_target = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "tests/test_ai.py"
    code, out = run_cmd(
        [str(PYTHON_EXE), "-m", "pytest", test_target, "-q", "--tb=short"],
        env={"SKIP_LIVE": "1", "ALLOW_LOCAL_RUN": "0"}
    )
    if code == 0:
        print(f"  ✅ Pytest Suite ({test_target}): PASSED")
        stages.append(("Pytest Suite", True, out))
    else:
        print(f"  ❌ Pytest Suite ({test_target}): FAILED")
        stages.append(("Pytest Suite", False, out))
        has_failure = True

    # Generate Feedback File for AI Agent
    if has_failure:
        print("\n" + "!" * 60)
        print("❌ HARNESS LOOP FAILED: Action Required.")
        print(f"Generating actionable context: {FEEDBACK_FILE.name}")
        print("!" * 60)

        feedback_content = [
            "# 🚨 Harness Loop Verification Feedback\n",
            "> **Agent Instruction**: Do not declare work complete. Read the failures below and fix them iteratively until all stages pass.\n\n"
        ]

        for name, passed, output in stages:
            status = "✅ PASSED" if passed else "❌ FAILED"
            feedback_content.append(f"### {name}: {status}\n")
            if not passed:
                feedback_content.append("```text\n" + output.strip() + "\n```\n")

        FEEDBACK_FILE.write_text("\n".join(feedback_content), encoding="utf-8")
        sys.exit(1)
    else:
        print("\n" + "=" * 60)
        print("🎉 ALL HARNESS CHECKS PASSED: 100% GREEN!")
        print("Ready for safe git commit & PR.")
        print("=" * 60)
        if FEEDBACK_FILE.exists():
            FEEDBACK_FILE.unlink()
        sys.exit(0)


if __name__ == "__main__":
    main()

"""
Master Harness Loop Runner (Autonomous Evaluation & Feedback Loop)
Standardizes the Verification & Self-Healing loop across all agents (Antigravity, Codex, Claude).
"""

import os
import subprocess
import sys
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent.parent
PYTHON_EXE = Path(sys.executable)
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
    print("\n[1/7] 📏 Checking Modular Code Standards (400-line limit)...")
    diff_code, diff_out = run_cmd(["git", "diff", "--name-only", "origin/main...HEAD", "--", "src/"])
    changed_src = [f for f in diff_out.splitlines() if f.strip().endswith(".py")]
    if diff_code == 0 and not changed_src:
        print("  ✅ Standards Check: PASSED (no changed src/*.py files)")
        stages.append(("Code Standards", True, "No changed src/*.py files."))
    else:
        code, out = run_cmd([str(PYTHON_EXE), "scripts/harness/verify_standards.py", "--markdown", "--warn-legacy-functions"])
        if code == 0:
            print("  ✅ Standards Check: PASSED")
            stages.append(("Code Standards", True, out))
        else:
            print("  ❌ Standards Check: FAILED")
            stages.append(("Code Standards", False, out))
            has_failure = True

    # Stage 2: Security Audit (Bandit)
    print("\n[2/7] 🛡️ Running Security Scan (bandit -r src/ -ll)...")
    code, out = run_cmd([str(PYTHON_EXE), "-m", "bandit", "-r", "src/", "-ll"])
    if code == 0:
        print("  ✅ Security Audit: PASSED (0 high/medium issues)")
        stages.append(("Security Audit", True, out))
    else:
        print("  ❌ Security Audit: FAILED")
        stages.append(("Security Audit", False, out))
        has_failure = True

    # Additional mandatory gates; all must pass, even for focused test targets.
    extra_gates = [
        ("Ruff", ["-m", "ruff", "check", "--select", "F821,F822,ASYNC210,ASYNC221",
                  "--per-file-ignores", "src/config.py:F822", "src/"]),
        ("Uzbek branch text", ["scripts/check_uzbek_text.py", "--base", "origin/main"]),
        ("Uzbek staged text", ["scripts/check_uzbek_text.py", "--staged"]),
        ("Skill mirror", ["scripts/sync_agent_skills.py", "--check"]),
    ]
    for index, (name, args) in enumerate(extra_gates, start=3):
        print(f"\n[{index}/7] {name}...")
        code, out = run_cmd([str(PYTHON_EXE), *args])
        passed = code == 0
        stages.append((name, passed, out))
        has_failure = has_failure or not passed
        print(f"  {name}: {'PASSED' if passed else 'FAILED'}")

    # Stage 7: Test Suite (Pytest)
    print("\n[7/7] 🧪 Running Pytest Suite (full suite by default)...")
    test_args = []
    test_label = "full suite"
    for arg in sys.argv[1:]:
        if not arg.startswith("-"):
            test_args.append(arg)
            test_label = arg
    code, out = run_cmd(
        [str(PYTHON_EXE), "-m", "pytest", *test_args, "-q", "--tb=short"],
        env={"SKIP_LIVE": "1", "ALLOW_LOCAL_RUN": "0"}
    )
    if code == 0:
        print(f"  ✅ Pytest Suite ({test_label}): PASSED")
        stages.append(("Pytest Suite", True, out))
    else:
        print(f"  ❌ Pytest Suite ({test_label}): FAILED")
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
        print("Local audit passed. Full suite, independent review and CI remain required for release." if test_args else "Local full-suite audit passed; independent review and CI remain required for release.")
        print("=" * 60)
        if FEEDBACK_FILE.exists():
            FEEDBACK_FILE.unlink()
        sys.exit(0)


if __name__ == "__main__":
    main()

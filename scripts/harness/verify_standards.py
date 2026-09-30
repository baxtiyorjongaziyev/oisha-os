"""
Code Standards Verifier (The Evaluator)
Checks for compliance with docs/agents/code-standards.md:
- Max 400 lines per production file in src/
- Max 60 lines per function
- AST syntax validation
"""

import ast
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

MAX_FILE_LINES = 400
MAX_FUNC_LINES = 60
TARGET_DIRS = ["src"]


def check_file(file_path: Path):
    violations = []
    try:
        content = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = file_path.read_text(encoding="latin-1")

    lines = content.splitlines()
    total_lines = len(lines)

    # 1. Check file line count
    if total_lines > MAX_FILE_LINES:
        violations.append({
            "type": "FILE_TOO_LONG",
            "file": str(file_path),
            "line": total_lines,
            "message": f"File has {total_lines} lines (exceeds {MAX_FILE_LINES} limit). Refactor into modular submodules."
        })

    # 2. Parse AST for function lengths and syntax
    try:
        tree = ast.parse(content, filename=str(file_path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if hasattr(node, "end_lineno") and node.end_lineno:
                    func_len = node.end_lineno - node.lineno + 1
                    if func_len > MAX_FUNC_LINES:
                        violations.append({
                            "type": "FUNC_TOO_LONG",
                            "file": str(file_path),
                            "line": node.lineno,
                            "name": node.name,
                            "message": f"Function '{node.name}' has {func_len} lines (exceeds {MAX_FUNC_LINES} limit). Decompose into helpers."
                        })
    except SyntaxError as e:
        violations.append({
            "type": "SYNTAX_ERROR",
            "file": str(file_path),
            "line": e.lineno,
            "message": f"Syntax error: {e.msg}"
        })

    return violations


def main():
    root = Path(__file__).resolve().parent.parent.parent
    all_violations = []
    scanned_files = 0

    for dir_name in TARGET_DIRS:
        target_dir = root / dir_name
        if not target_dir.exists():
            continue

        for p in target_dir.rglob("*.py"):
            if "__pycache__" in str(p) or "legacy" in str(p):
                continue
            scanned_files += 1
            violations = check_file(p)
            all_violations.extend(violations)

    output_format = "markdown" if "--markdown" in sys.argv else "text"

    if output_format == "markdown":
        if not all_violations:
            print("## Code Standards Audit: PASSED\n")
            print(f"- **Scanned Files**: {scanned_files}")
            print(f"- **God-files (> {MAX_FILE_LINES} lines)**: 0")
            print(f"- **Oversized Functions (> {MAX_FUNC_LINES} lines)**: 0")
            print("- **Status**: All code complies with modular standards.")
        else:
            print(f"## Code Standards Audit: FAILED ({len(all_violations)} violations)\n")
            for v in all_violations:
                print(f"- **[{v['type']}]** `{v['file']}:{v['line']}` — {v['message']}")
            print("\n> **Action Required**: Decompose God-files and oversized functions using the Facade pattern.")
    else:
        print(f"Scanned {scanned_files} files across {TARGET_DIRS}...")
        if not all_violations:
            print(f"SUCCESS: All {scanned_files} files comply with code standards (<= {MAX_FILE_LINES} lines).")
        else:
            print(f"WARNING/FAILED: Found {len(all_violations)} violations:")
            for v in all_violations:
                print(f"  [{v['type']}] {v['file']}:{v['line']} - {v['message']}")

    # Only exit with error if there are file length violations or syntax errors
    has_critical = any(v["type"] in ("FILE_TOO_LONG", "SYNTAX_ERROR") for v in all_violations)
    sys.exit(1 if has_critical else 0)


if __name__ == "__main__":
    main()

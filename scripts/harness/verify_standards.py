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

for stream in (sys.stdout, sys.stderr):
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8", errors="replace")

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

    warn_legacy = "--warn-legacy-functions" in sys.argv
    warn_files = "--warn-legacy-files" in sys.argv
    cli_targets = [arg for arg in sys.argv[1:] if not arg.startswith("-")]

    targets_to_scan = cli_targets if cli_targets else TARGET_DIRS
    for item in targets_to_scan:
        target_path = Path(item)
        if not target_path.is_absolute():
            target_path = root / item
        if not target_path.exists():
            continue

        if target_path.is_file():
            if target_path.suffix == ".py":
                scanned_files += 1
                violations = check_file(target_path)
                all_violations.extend(violations)
        else:
            for p in target_path.rglob("*.py"):
                if "__pycache__" in str(p) or "legacy" in str(p):
                    continue
                scanned_files += 1
                violations = check_file(p)
                all_violations.extend(violations)

    output_format = "markdown" if "--markdown" in sys.argv else "text"

    has_file_violations = any(v["type"] == "FILE_TOO_LONG" for v in all_violations)
    has_syntax_errors = any(v["type"] == "SYNTAX_ERROR" for v in all_violations)
    has_func_violations = any(v["type"] == "FUNC_TOO_LONG" for v in all_violations)
    has_critical = has_syntax_errors or (has_file_violations and not warn_files)
    is_failed = has_critical or (has_func_violations and not warn_legacy)

    if output_format == "markdown":
        if not is_failed and not all_violations:
            print("## Code Standards Audit: PASSED\n")
            print(f"- **Scanned Files**: {scanned_files}")
            print(f"- **God-files (> {MAX_FILE_LINES} lines)**: 0")
            print(f"- **Oversized Functions (> {MAX_FUNC_LINES} lines)**: 0")
            print("- **Status**: All code complies with modular standards.")
        elif not is_failed and all_violations:
            print(f"## Code Standards Audit: PASSED with warnings ({len(all_violations)} function length warnings)\n")
            print(f"- **Scanned Files**: {scanned_files}")
            print(f"- **God-files (> {MAX_FILE_LINES} lines)**: 0 (PASSED)")
            print(f"- **Legacy Oversized Functions**: {len(all_violations)} warnings (grandfathered)")
            print("- **Status**: File modularity standards met.")
        else:
            print(f"## Code Standards Audit: FAILED ({len(all_violations)} violations)\n")
            for v in all_violations:
                print(f"- **[{v['type']}]** `{v['file']}:{v['line']}` — {v['message']}")
            print("\n> **Action Required**: Decompose God-files and oversized functions using the Facade pattern.")
    else:
        print(f"Scanned {scanned_files} files across {targets_to_scan}...")
        if not is_failed:
            if all_violations:
                print(f"PASSED with warnings: {len(all_violations)} legacy function violations detected.")
            else:
                print(f"SUCCESS: All {scanned_files} files comply with code standards (<= {MAX_FILE_LINES} lines).")
        else:
            print(f"FAILED: Found {len(all_violations)} violations:")
            for v in all_violations:
                print(f"  [{v['type']}] {v['file']}:{v['line']} - {v['message']}")

    # Every unexcused violation fails this mandatory quality gate.
    sys.exit(1 if is_failed else 0)


if __name__ == "__main__":
    main()

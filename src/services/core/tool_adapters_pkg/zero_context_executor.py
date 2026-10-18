"""
Zero-Context Tool Execution Engine (Hermes-Style Batch Scripting)
Enables agent multi-step RPC execution in a single turn without
polluting the LLM context window with intermediate raw outputs.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import structlog

logger = structlog.get_logger("ZeroContextExecutor")

ROOT = Path(__file__).resolve().parent.parent.parent.parent
PYTHON_EXE = ROOT / ".venv" / "Scripts" / "python.exe"
if not PYTHON_EXE.exists():
    PYTHON_EXE = Path(sys.executable)

DANGEROUS_PATTERNS = [
    "rm -rf",
    "git reset --hard",
    "git push --force",
    "shutil.rmtree",
    "os.remove",
]


@dataclass
class ExecutionResult:
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    stdout: str = ""
    error: Optional[str] = None
    execution_time_ms: int = 0


class ZeroContextExecutor:
    """Executes atomic Python scripts to consolidate multi-tool operations."""

    def __init__(self, root_dir: Optional[Path] = None, timeout_seconds: int = 45):
        self.root_dir = root_dir or ROOT
        self.timeout_seconds = timeout_seconds

    def _validate_safety(self, code: str) -> None:
        """Blocks obviously destructive code before running."""
        for pattern in DANGEROUS_PATTERNS:
            if pattern in code:
                raise ValueError(f"Blocked dangerous pattern in script: '{pattern}'")

    def _prepare_environment(self, custom_env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Prepares isolated environment with project PYTHONPATH and safety flags."""
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.root_dir)
        env["SKIP_LIVE"] = env.get("SKIP_LIVE", "1")
        env["ALLOW_LOCAL_RUN"] = "0"
        if custom_env:
            env.update(custom_env)
        return env

    def _extract_json_payload(self, stdout: str) -> Dict[str, Any]:
        """Extracts JSON payload if emitted by the script, or returns raw lines."""
        lines = stdout.strip().splitlines()
        for line in reversed(lines):
            line_str = line.strip()
            if line_str.startswith("{") and line_str.endswith("}"):
                try:
                    return json.loads(line_str)
                except Exception:
                    continue
        return {"raw_output": stdout[-1000:] if len(stdout) > 1000 else stdout}

    def _run_process(self, tmp_path: Path, env: Dict[str, str], timeout_val: int) -> subprocess.CompletedProcess:
        """Executes the temporary python file safely."""
        return subprocess.run(
            [str(PYTHON_EXE), str(tmp_path)],
            cwd=str(self.root_dir),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_val,
        )

    def execute_script(
        self,
        script_code: str,
        custom_env: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
    ) -> ExecutionResult:
        """Executes a self-contained script snippet and returns parsed structured data."""
        self._validate_safety(script_code)
        import time

        start_time = time.time()
        timeout_val = timeout or self.timeout_seconds
        env = self._prepare_environment(custom_env)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", encoding="utf-8", delete=False) as tmp:
            tmp.write(script_code)
            tmp_path = Path(tmp.name)

        try:
            res = self._run_process(tmp_path, env, timeout_val)
            elapsed_ms = int((time.time() - start_time) * 1000)

            if res.returncode == 0:
                payload = self._extract_json_payload(res.stdout)
                return ExecutionResult(success=True, data=payload, stdout=res.stdout[-500:], execution_time_ms=elapsed_ms)

            err_msg = res.stderr.strip() or res.stdout.strip()
            logger.warning("Zero-context script failed", exit_code=res.returncode, error=err_msg[:200])
            return ExecutionResult(success=False, error=err_msg[-1000:], stdout=res.stdout[-300:], execution_time_ms=elapsed_ms)
        except subprocess.TimeoutExpired:
            return ExecutionResult(success=False, error=f"Script timed out after {timeout_val}s", execution_time_ms=int((time.time() - start_time) * 1000))
        except Exception as exc:
            return ExecutionResult(success=False, error=str(exc))
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass


    def execute_batch_tasks(self, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Runs a list of declarative operations and aggregates summary results."""
        results = []
        for task in tasks:
            task_name = task.get("name", "anonymous_task")
            code = task.get("code", "")
            if not code:
                continue
            res = self.execute_script(code)
            results.append({"task": task_name, "success": res.success, "data": res.data, "error": res.error})
        return {"total": len(results), "passed": sum(1 for r in results if r["success"]), "details": results}

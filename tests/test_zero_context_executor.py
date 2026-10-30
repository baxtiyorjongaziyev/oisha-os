"""
Unit tests for ZeroContextExecutor (Hermes-Style Token-Efficient Scripting)
"""

import pytest
from src.services.core.tool_adapters_pkg.zero_context_executor import ZeroContextExecutor


def test_zero_context_executor_success():
    executor = ZeroContextExecutor(timeout_seconds=10)
    code = """
import json
print("Status log line 1")
print(json.dumps({"success": True, "count": 42, "status": "ok"}))
"""
    result = executor.execute_script(code)
    assert result.success is True
    assert result.data.get("count") == 42
    assert result.data.get("status") == "ok"


def test_zero_context_executor_safety_block():
    executor = ZeroContextExecutor(timeout_seconds=5)
    dangerous_code = "import os; os.system('rm -rf /')"
    with pytest.raises(ValueError) as exc:
        executor.execute_script(dangerous_code)
    assert "Blocked dangerous pattern" in str(exc.value)


def test_zero_context_executor_batch():
    executor = ZeroContextExecutor(timeout_seconds=10)
    tasks = [
        {"name": "t1", "code": "import json; print(json.dumps({'res': 1}))"},
        {"name": "t2", "code": "import json; print(json.dumps({'res': 2}))"},
    ]
    summary = executor.execute_batch_tasks(tasks)
    assert summary["total"] == 2
    assert summary["passed"] == 2

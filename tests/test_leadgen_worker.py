import asyncio
import json
import pytest
from pathlib import Path
from unittest.mock import patch
from src.workers.leadgen_worker import heartbeat_loop, HEARTBEAT_PATH


@pytest.mark.asyncio
async def test_heartbeat_loop(tmp_path):
    mock_heartbeat_path = tmp_path / "leadgen_heartbeat.json"

    with patch("src.workers.leadgen_worker.HEARTBEAT_PATH", mock_heartbeat_path), \
         patch("src.services.core.instagram.leadgen_watchdog.audit_leadgen_health") as mock_audit:
        mock_audit.return_value = {"status": "healthy", "total": 10}

        task = asyncio.create_task(heartbeat_loop())
        await asyncio.sleep(0.05)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

        assert mock_heartbeat_path.exists()
        data = json.loads(mock_heartbeat_path.read_text(encoding="utf-8"))
        assert data["status"] == "healthy"
        assert data["stats"]["total"] == 10

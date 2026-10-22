import asyncio
import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace

import pytest


def helper():
    path = Path(__file__).with_name("tn_audit_qr.py")
    spec = importlib.util.spec_from_file_location("tn_audit_qr", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_session_is_memory_only_disconnected_before_audit_and_restored(monkeypatch):
    module = helper()
    monkeypatch.setenv("TN_AUDIT_SESSION_STRING", "synthetic-before")
    calls = []

    async def disconnect():
        calls.append("disconnect")

    async def audit():
        calls.append("audit")
        assert os.environ["TN_AUDIT_SESSION_STRING"] == "synthetic-new"

    client = SimpleNamespace(
        session=SimpleNamespace(save=lambda: "synthetic-new"), disconnect=disconnect
    )
    asyncio.run(module.run_audit(client, audit))
    assert calls == ["disconnect", "audit"]
    assert os.environ["TN_AUDIT_SESSION_STRING"] == "synthetic-before"


def test_audit_failure_clears_ephemeral_session(monkeypatch):
    module = helper()
    monkeypatch.delenv("TN_AUDIT_SESSION_STRING", raising=False)

    async def disconnect():
        pass

    async def audit():
        raise RuntimeError("synthetic failure")

    client = SimpleNamespace(
        session=SimpleNamespace(save=lambda: "synthetic-new"), disconnect=disconnect
    )
    with pytest.raises(RuntimeError, match="synthetic failure"):
        asyncio.run(module.run_audit(client, audit))
    assert "TN_AUDIT_SESSION_STRING" not in os.environ


def test_wrong_account_is_rejected():
    module = helper()
    with pytest.raises(ValueError, match="owner"):
        module.validate_owner(SimpleNamespace(id=200), 100)

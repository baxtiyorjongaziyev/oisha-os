"""Fail-safe behaviour of the tiered auto-reply gate.

Guards the invariant the Owner asked for: the userbot must NOT auto-reply on its
own. The default (env unset) is 'shadow' — draft for approval, never send — and
even @mentions and the kill switch cannot turn shadow into an autonomous send.
"""

import pytest

from src.services.core import auto_reply_gate


class _FakeDB:
    """Minimal db stub: get_state returns preset values (None = no override)."""

    def __init__(self, state=None):
        self._state = state or {}

    async def get_state(self, key):
        return self._state.get(key)


@pytest.mark.asyncio
async def test_default_mode_is_shadow_not_autosend(monkeypatch):
    monkeypatch.delenv("AUTO_REPLY_MODE", raising=False)
    decision = await auto_reply_gate.evaluate(_FakeDB(), message_text="salom")
    assert decision.action == "shadow"
    assert decision.effective_mode == "shadow"


@pytest.mark.asyncio
async def test_shadow_never_autosends_even_on_mention(monkeypatch):
    monkeypatch.setenv("AUTO_REPLY_MODE", "shadow")
    decision = await auto_reply_gate.evaluate(
        _FakeDB(), is_mentioned=True, message_text="@oisha javob ber"
    )
    assert decision.action == "shadow"  # mention must NOT force a send in shadow


@pytest.mark.asyncio
async def test_off_mode_skips(monkeypatch):
    monkeypatch.setenv("AUTO_REPLY_MODE", "off")
    decision = await auto_reply_gate.evaluate(
        _FakeDB(), is_mentioned=True, message_text="salom"
    )
    assert decision.action == "skip"


@pytest.mark.asyncio
async def test_escalation_trigger_wins(monkeypatch):
    monkeypatch.setenv("AUTO_REPLY_MODE", "live")
    decision = await auto_reply_gate.evaluate(
        _FakeDB(), is_mentioned=True, message_text="bu firibgar, sudga beraman"
    )
    assert decision.action == "escalate"


@pytest.mark.asyncio
async def test_kill_switch_overrides_mention(monkeypatch):
    monkeypatch.setenv("AUTO_REPLY_MODE", "live")
    db = _FakeDB({auto_reply_gate.FLAG_KILL_SWITCH: "false"})  # pulled
    decision = await auto_reply_gate.evaluate(
        db, is_mentioned=True, message_text="salom"
    )
    assert decision.action == "skip"
    assert decision.kill_switch_on is True


@pytest.mark.asyncio
async def test_live_mode_autosends(monkeypatch):
    monkeypatch.setenv("AUTO_REPLY_MODE", "live")
    decision = await auto_reply_gate.evaluate(_FakeDB(), message_text="salom")
    assert decision.action == "send"


@pytest.mark.asyncio
async def test_db_mode_override_beats_env(monkeypatch):
    monkeypatch.setenv("AUTO_REPLY_MODE", "live")
    db = _FakeDB({auto_reply_gate.FLAG_MODE: "shadow"})
    decision = await auto_reply_gate.evaluate(db, message_text="salom")
    assert decision.effective_mode == "shadow"
    assert decision.action == "shadow"

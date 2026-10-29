"""Unit tests for Hermes Harness Loop, Invariant Verification, and Context Engine."""
from __future__ import annotations

import asyncio
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.core.ai.hermes_context import (
    HermesContextEngine,
    HermesSessionStore,
    get_hermes_session_store,
)
from src.services.core.ai.hermes_harness import (
    HermesCircuitBreaker,
    HermesHarnessLoop,
    HermesInvariantEvaluator,
)
from src.services.core.ai.hermes_provider import (
    HermesAgentProvider,
    extract_session_id,
    clean_hermes_output,
)


def test_extract_session_id():
    raw_quiet = (
        "session_id: 20261027_135029_cc8583\n"
        "Assalomu alaykum! Men yordamga tayyorman."
    )
    assert extract_session_id(raw_quiet) == "20261027_135029_cc8583"

    raw_resume = (
        "Resume this session with:\n"
        "  hermes --resume 20261027_112233_abc123\n"
    )
    assert extract_session_id(raw_resume) == "20261027_112233_abc123"


def test_clean_hermes_output_quiet_mode():
    raw = (
        "session_id: 20261027_135029_cc8583\n"
        "Oisha-OS — Jon Branding agentligining bosh operatsion tizimidir."
    )
    cleaned = clean_hermes_output(raw)
    assert cleaned == "Oisha-OS — Jon Branding agentligining bosh operatsion tizimidir."
    assert "session_id:" not in cleaned


def test_invariant_evaluator_valid_human_text():
    good_text = (
        "Assalomu alaykum! Hozir uchrashuvdaman. "
        "Xabaringizni ko'rdim, tez orada shaxsan o'zim batafsil javob yozaman."
    )
    res = HermesInvariantEvaluator.evaluate(good_text, destination="telegram_dm")
    assert res.is_valid is True
    assert len(res.violations) == 0


def test_invariant_evaluator_detects_ai_slop():
    slop_text = (
        "Assalomu alaykum! Men sun'iy intellekt yordamchisiman. "
        "Sizga yana qanday yordam bera olaman?"
    )
    res = HermesInvariantEvaluator.evaluate(slop_text, destination="telegram_dm")
    assert res.is_valid is False
    assert any("AI / robot yordamchi" in v for v in res.violations)
    assert res.critic_prompt is not None


def test_invariant_evaluator_detects_hallucinations():
    hallucination_text = (
        "Biz sizga logotipni $50 ga qilib beramiz va 100% kafolatli natija beramiz!"
    )
    res = HermesInvariantEvaluator.evaluate(hallucination_text, destination="general")
    assert res.is_valid is False
    assert any("Asossiz kafolat yoki uydirma narx" in v for v in res.violations)


def test_invariant_evaluator_formatting_dm_violations():
    codeblock_text = "Salom! Mana sizga javob:\n```python\nprint('salom')\n```"
    res = HermesInvariantEvaluator.evaluate(codeblock_text, destination="telegram_dm")
    assert res.is_valid is False
    assert any("kod bloklari" in v for v in res.violations)


def test_circuit_breaker_transitions():
    cb = HermesCircuitBreaker(failure_threshold=2, recovery_timeout=0.2)
    assert cb.is_available() is True
    assert cb.state == "CLOSED"

    # 1st failure
    cb.record_failure()
    assert cb.state == "CLOSED"
    assert cb.is_available() is True

    # 2nd failure -> TRIPPED
    cb.record_failure()
    assert cb.state == "OPEN"
    assert cb.is_available() is False

    # Wait for recovery timeout
    time.sleep(0.25)
    assert cb.is_available() is True
    assert cb.state == "HALF_OPEN"

    # Successful call recovers circuit
    cb.record_success()
    assert cb.state == "CLOSED"
    assert cb.consecutive_failures == 0


def test_session_store_mapping_and_expiry():
    store = HermesSessionStore(ttl_seconds=0.2)
    store.set_session("telegram", "user_123", "sess_001")
    assert store.get_session("telegram", "user_123") == "sess_001"
    assert store.total_active_sessions() == 1

    time.sleep(0.25)
    # Expired
    assert store.get_session("telegram", "user_123") is None
    assert store.total_active_sessions() == 0


def test_context_engine_prompts():
    copilot_prompt = HermesContextEngine.build_copilot_system_prompt("Rayxon")
    assert "Rayxon" in copilot_prompt
    assert "Jon Branding" in copilot_prompt
    assert "skript" in copilot_prompt

    dm_prompt = HermesContextEngine.build_dm_responder_system_prompt()
    assert "Baxtiyorjon Gaziyev" in dm_prompt
    assert "bot" in dm_prompt.lower()

    consult_prompt = HermesContextEngine.build_branding_consultant_prompt()
    assert "brend strategiyasi" in consult_prompt


@pytest.mark.asyncio
async def test_harness_loop_self_healing_flow():
    harness = HermesHarnessLoop(max_refinements=2)

    responses = [
        # Turn 0: Violates invariants (contains AI slop)
        "Albatta, men sizga yordam berishdan xursandman. Men sun'iy intellekt yordamchisiman.",
        # Turn 1: Self-healed valid response
        "Assalomu alaykum! Hozir uchrashuvdaman, tez orada shaxsan yozaman.",
    ]
    call_index = 0

    async def mock_generator(p: str, s: str = None):
        nonlocal call_index
        resp = responses[call_index]
        call_index += 1
        return resp

    result = await harness.execute_loop(
        generate_fn=mock_generator,
        prompt="Salom",
        destination="telegram_dm",
    )

    assert result == "Assalomu alaykum! Hozir uchrashuvdaman, tez orada shaxsan yozaman."
    assert call_index == 2  # Proves self-healing turn was triggered
    telemetry = harness.telemetry.as_dict()
    assert telemetry["successful_requests"] == 1
    assert telemetry["refinement_turns"] == 1


@pytest.mark.asyncio
async def test_hermes_provider_with_harness():
    provider = HermesAgentProvider()
    # The suite exercises the global harness singleton (circuit breaker can be
    # left OPEN by earlier tests), so isolate with a fresh harness instance.
    from src.services.core.ai.hermes_harness import HermesHarnessLoop
    fresh_harness = HermesHarnessLoop()
    with patch(
        "src.services.core.ai.hermes_provider.get_hermes_harness",
        return_value=fresh_harness,
    ), patch.object(
        provider,
        "execute_raw_turn",
        new_callable=AsyncMock,
        return_value=("Salom, loyiha bo'yicha gaplashamiz.", "sess_999"),
    ):
        reply = await provider.generate_response(
            prompt="Salom",
            destination="telegram_dm",
            use_harness=True,
        )
        assert reply == "Salom, loyiha bo'yicha gaplashamiz."


@pytest.mark.asyncio
async def test_harness_fails_closed_when_still_invalid():
    harness = HermesHarnessLoop(max_refinements=1)

    async def always_bad(p: str, s: str = None):
        return "Biz logotipni $50 ga qilamiz va 100% kafolatli natija beramiz!"

    result = await harness.execute_loop(
        generate_fn=always_bad, prompt="Narx?", destination="general"
    )

    assert result is None
    telemetry = harness.telemetry.as_dict()
    assert telemetry["failed_requests"] == 1
    assert telemetry["successful_requests"] == 0


@pytest.mark.asyncio
async def test_harness_returns_sanitized_text_only_if_it_passes():
    harness = HermesHarnessLoop(max_refinements=1)

    async def stubborn(p: str, s: str = None):
        return "Loyiha bo'yicha ertaga gaplashamiz. Har qanday savolingiz bo'lsa yozing."

    result = await harness.execute_loop(
        generate_fn=stubborn, prompt="Salom", destination="general"
    )

    assert result is not None
    assert "savolingiz" not in result.lower()
    assert "Loyiha bo'yicha ertaga gaplashamiz." in result


class _FakeProc:
    def __init__(self, returncode, out=b"", err=b"", hang=False):
        self.returncode = returncode
        self._out, self._err, self._hang = out, err, hang
        self.kill = MagicMock(side_effect=self._kill)

    def _kill(self):
        self.returncode = -9

    async def communicate(self):
        if self._hang:
            await asyncio.sleep(30)
        return self._out, self._err

    async def wait(self):
        return self.returncode


@pytest.mark.asyncio
async def test_provider_nonzero_exit_is_not_a_reply():
    provider = HermesAgentProvider()
    proc = _FakeProc(1, out=b"Traceback (most recent call last): boom", err=b"err")
    with patch.object(provider, "find_executable", return_value="hermes"), patch(
        "asyncio.create_subprocess_exec", AsyncMock(return_value=proc)
    ):
        reply, sess = await provider.execute_raw_turn("Salom", timeout=5)

    assert reply is None
    assert sess is None


@pytest.mark.asyncio
async def test_provider_timeout_kills_subprocess():
    provider = HermesAgentProvider()
    proc = _FakeProc(None, hang=True)
    with patch.object(provider, "find_executable", return_value="hermes"), patch(
        "asyncio.create_subprocess_exec", AsyncMock(return_value=proc)
    ):
        reply, sess = await provider.execute_raw_turn("Salom", timeout=0.05)

    assert reply is None
    assert sess is None
    proc.kill.assert_called_once()

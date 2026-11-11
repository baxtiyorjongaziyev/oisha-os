"""Naming / Trademark / Packaging / ReelsScript agentlari va ularning routingi."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.agents.naming_agent import NAMING_SUFFIX, NamingAgent
from src.agents.orchestrator import AGENT_IDS, AgentOrchestrator
from src.agents.packaging_agent import PACKAGING_SUFFIX, PackagingAgent
from src.agents.reels_script_agent import REELS_SCRIPT_SUFFIX, ReelsScriptAgent
from src.agents.trademark_agent import TRADEMARK_SUFFIX, TrademarkAgent

AGENTS = [
    ("naming", NamingAgent, NAMING_SUFFIX),
    ("trademark", TrademarkAgent, TRADEMARK_SUFFIX),
    ("packaging", PackagingAgent, PACKAGING_SUFFIX),
    ("reels_script", ReelsScriptAgent, REELS_SCRIPT_SUFFIX),
]


def _fallback(message: str) -> str:
    manager = SimpleNamespace(get_agent=lambda agent_id: None)
    return AgentOrchestrator(manager)._route_intent_fallback(message)


@pytest.mark.parametrize(
    "message, expected",
    [
        ("Kafemizga nom kerak, naming qilib bering", "naming"),
        ("Tovar belgisini qanday himoya qilamiz?", "trademark"),
        ("Logoga patent olish kerakmi", "trademark"),
        ("Sharbat uchun qadoq dizayni kerak", "packaging"),
        ("Yangi etiketka chizdirmoqchimiz", "packaging"),
        ("Reels uchun ssenariy yozib bering", "reels_script"),
        # Mavjud yoʻnalishlar buzilmagan
        ("Instagram uchun post yoz", "copywriter"),
        ("Narx qancha?", "sales"),
    ],
)
def test_fallback_routing(message, expected):
    assert _fallback(message) == expected


@pytest.mark.parametrize("agent_id, _cls, _suffix", AGENTS)
def test_new_agents_are_routable(agent_id, _cls, _suffix):
    assert agent_id in AGENT_IDS


@pytest.mark.asyncio
@pytest.mark.parametrize("agent_id, agent_cls, suffix", AGENTS)
async def test_process_task_sends_context_without_touching_prompt(
    agent_id, agent_cls, suffix
):
    agent = agent_cls(agent_id, "BASE" + suffix, {})
    with patch.object(
        agent, "call_ai_with_fallback", new_callable=AsyncMock, return_value="javob"
    ) as mock_ai, patch.object(agent, "load_session_history", new_callable=AsyncMock):
        reply = await agent.process_task(
            7, "Yordam kerak", context={"brand_name": "Asl", "business_type": "kafe"}
        )

    assert reply == "javob"
    contents = mock_ai.await_args.args[0]
    assert mock_ai.await_args.kwargs["enable_tools"] is False
    last_text = contents[-1]["parts"][0]["text"]
    assert last_text.startswith("Yordam kerak")
    assert "Asl" in last_text and "kafe" in last_text
    # Kontekst promptga yoki saqlangan tarixga sizib chiqmaydi
    assert agent.system_prompt == "BASE" + suffix
    assert agent.get_session_history(7) == [
        {"role": "user", "content": "Yordam kerak"},
        {"role": "assistant", "content": "javob"},
    ]


@pytest.mark.asyncio
async def test_process_task_without_context_adds_no_note():
    agent = NamingAgent("naming", "BASE", {})
    with patch.object(
        agent, "call_ai_with_fallback", new_callable=AsyncMock, return_value="ok"
    ) as mock_ai, patch.object(agent, "load_session_history", new_callable=AsyncMock):
        await agent.process_task(1, "Salom")

    assert mock_ai.await_args.args[0] == [
        {"role": "user", "parts": [{"text": "Salom"}]}
    ]


def test_legal_and_fact_guardrails_present_in_prompts():
    assert "TEKSHIRMAGANSIZ" in NAMING_SUFFIX
    assert "TEKSHIRMAGANSIZ" in TRADEMARK_SUFFIX
    assert "patent vakili" in TRADEMARK_SUFFIX
    assert "aniqlanmagan" in PACKAGING_SUFFIX
    assert "haqiqiy raqam" in REELS_SCRIPT_SUFFIX

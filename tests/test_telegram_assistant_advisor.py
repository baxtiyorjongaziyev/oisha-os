import pytest
from pathlib import Path
from src.services.core.assistant.telegram_assistant_advisor import TelegramAssistantAdvisor, SHAHNOZA_USER_ID


def test_analyze_chat_pricing_request():
    advisor = TelegramAssistantAdvisor()
    chat_messages = [
        {"id": 1, "sender_id": 9999, "sender": "Kamila Pardalari", "text": "Assalomu alaykum, logotip narxi qancha bo'ladi?"}
    ]
    task = advisor.analyze_chat_for_assistant(
        chat_id=-1003803487986,
        chat_title="Kamila Pardalari",
        messages=chat_messages,
        owner_id=150074828,
    )
    assert task is not None
    assert task["action_type"] == "Narx / Byudjet so'rovi"
    assert "Kamila Pardalari" in task["chat_title"]
    assert "portfolio" in task["recommendation"]


def test_analyze_chat_ignore_owner_and_assistant():
    advisor = TelegramAssistantAdvisor()
    # Owner message
    owner_msg = [{"id": 2, "sender_id": 150074828, "sender": "Baxtiyorjon", "text": "Xop, ko'rib beramiz"}]
    task = advisor.analyze_chat_for_assistant(123, "Test", owner_msg, owner_id=150074828)
    assert task is None

    # Assistant message
    assistant_msg = [{"id": 3, "sender_id": SHAHNOZA_USER_ID, "sender": "Shahnoza", "text": "Hozir yuboraman"}]
    task2 = advisor.analyze_chat_for_assistant(123, "Test", assistant_msg, owner_id=150074828)
    assert task2 is None


def test_record_in_obsidian(tmp_path: Path):
    vault = tmp_path / "TestVault"
    (vault / "20-Areas").mkdir(parents=True)

    advisor = TelegramAssistantAdvisor(vault_path=vault)
    tasks = [
        {
            "chat_title": "Kamila Pardalari",
            "action_type": "Loyiha statusi",
            "recommendation": "Mijozga 2 ta yangi logotip variantini yuboring.",
            "text": "Logotip qachon tayyor bo'ladi?",
        }
    ]
    success = advisor.record_in_obsidian(tasks)
    assert success is True

    note = vault / "20-Areas" / "Yordamchi Vazifalari.md"
    assert note.exists()
    content = note.read_text(encoding="utf-8")
    assert "Kamila Pardalari" in content
    assert "Mijozga 2 ta yangi logotip variantini yuboring" in content

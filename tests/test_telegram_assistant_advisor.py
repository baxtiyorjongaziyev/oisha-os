import pytest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from src.services.core.assistant.telegram_assistant_advisor import (
    SHAHNOZA_USER_ID,
    TelegramAssistantAdvisor,
    detect_calendar_appointment,
)

TZ = ZoneInfo("Asia/Tashkent")
OWNER_ID = 150074828


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

# --- Kalendar taklifi (uchrashuv kelishuvi) -----------------------------------

MEETING_TEXT = (
    "Shanba kuni 10:00 ga offline uchrashuvga kelishdik Nuriddin aka bilan "
    "Patent ishlarini boshlemiz OOMAR loyihasi bo'yicha"
)


def test_detect_appointment_weekday():
    reference = datetime(2026, 11, 3, 9, 0, tzinfo=TZ)  # seshanba
    proposal = detect_calendar_appointment(MEETING_TEXT, reference=reference)

    assert proposal is not None
    assert proposal["start_iso"] == "2026-11-07T10:00:00+05:00"
    assert proposal["end_iso"] == "2026-11-07T11:00:00+05:00"
    assert proposal["when_label"].startswith("shanba, 07.11.2026 10:00")


def test_detect_appointment_requires_date():
    reference = datetime(2026, 11, 3, 9, 0, tzinfo=TZ)
    assert detect_calendar_appointment("10:00 da uchrashamiz", reference=reference) is None
    assert detect_calendar_appointment("Ertaga gaplashamiz", reference=reference) is None


def test_detect_appointment_past_datetime_is_ignored():
    reference = datetime(2026, 11, 7, 12, 0, tzinfo=TZ)
    assert detect_calendar_appointment("07.11.2026 10:00 da uchrashuv", reference=reference) is None


def test_detect_appointment_handles_typographic_apostrophe():
    reference = datetime(2026, 11, 3, 9, 0, tzinfo=TZ)
    proposal = detect_calendar_appointment("Payshanba 15:30 da ko\u2019rishamiz", reference=reference)
    assert proposal is not None
    assert proposal["start_iso"] == "2026-11-05T15:30:00+05:00"


def test_analyze_owner_message_with_appointment_proposes_calendar():
    advisor = TelegramAssistantAdvisor()
    messages = [{"id": 11, "sender_id": OWNER_ID, "sender": "Baxtiyorjon", "text": MEETING_TEXT}]

    task = advisor.analyze_chat_for_assistant(
        chat_id=-1003114662117,
        chat_title="Loyihalar guruhi",
        messages=messages,
        owner_id=OWNER_ID,
        reference_dt=datetime(2026, 11, 3, 9, 0, tzinfo=TZ),
    )

    assert task is not None
    assert task["action_type"] == "Uchrashuv / Kalendar"
    assert "kiritib qo\u02bbyaymi" in task["recommendation"]
    assert task["calendar"]["when_label"].startswith("shanba, 07.11.2026 10:00")

    alert = advisor.format_telegram_alert(task)
    assert "Baxtiyorjon Gaziyev kalendariga kiritib qo\u02bbyaymi?" in alert


def test_analyze_client_appointment_uses_calendar_branch():
    advisor = TelegramAssistantAdvisor()
    messages = [{"id": 12, "sender_id": 777, "sender": "Nuriddin aka", "text": MEETING_TEXT}]

    task = advisor.analyze_chat_for_assistant(
        chat_id=555,
        chat_title="Nuriddin aka",
        messages=messages,
        owner_id=OWNER_ID,
        reference_dt=datetime(2026, 11, 3, 9, 0, tzinfo=TZ),
    )

    assert task is not None
    assert task["action_type"] == "Uchrashuv / Kalendar"
    assert "calendar" in task

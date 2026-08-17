from types import SimpleNamespace

import pytest

from src.services.core.admin_aiogram_dispatcher import (
    AiogramCallbackEventAdapter,
    build_admin_aiogram_dispatcher,
    handle_aiogram_chatid,
    handle_aiogram_command_center,
    handle_aiogram_finance_risks,
    handle_aiogram_oisha_stats,
    handle_aiogram_project_risks,
    handle_aiogram_sales_today,
    handle_aiogram_team_capacity,
    maybe_build_admin_aiogram_dispatcher,
)


class _EditableMessage:
    text = "old"

    def __init__(self):
        self.edits = []
        self.markup_edits = []

    async def edit_text(self, text, **kwargs):
        self.edits.append((text, kwargs))

    async def edit_reply_markup(self, reply_markup=None):
        self.markup_edits.append(reply_markup)


class _Callback:
    data = "happrove:1:business"

    def __init__(self):
        self.message = _EditableMessage()
        self.answers = []

    async def answer(self, text=""):
        self.answers.append(text)


async def test_aiogram_callback_adapter_supports_hisobchi_surface():
    callback = _Callback()
    event = AiogramCallbackEventAdapter(callback)

    await event.answer("OK")
    await event.edit("Updated", parse_mode="html")

    assert event.data == "happrove:1:business"
    assert callback.answers == ["OK"]
    assert callback.message.edits == [("Updated", {"parse_mode": "HTML", "reply_markup": None})]

    # Test editing buttons only
    await event.edit(buttons=[[{"text": "Btn", "data": "test_data"}]])
    assert len(callback.message.markup_edits) == 1


class FakeAiogramMessage:
    def __init__(
        self,
        *,
        text="/start",
        user_id=150074828,
        chat_id=-100123,
        title="Team",
        thread_id=None,
    ):
        self.text = text
        self.from_user = SimpleNamespace(id=user_id)
        self.chat = SimpleNamespace(id=chat_id, title=title, first_name=None)
        self.message_thread_id = thread_id
        self.reply_to_message = None
        self.answers = []

    async def answer(self, text, **kwargs):
        self.answers.append((text, kwargs))


@pytest.mark.asyncio
async def test_aiogram_chatid_handler_uses_shared_router():
    message = FakeAiogramMessage(text="/chatid", thread_id=77)

    await handle_aiogram_chatid(message)

    assert "<code>-100123</code>" in message.answers[0][0]
    assert "<code>77</code>" in message.answers[0][0]
    assert message.answers[0][1]["parse_mode"] == "html"


@pytest.mark.asyncio
async def test_aiogram_stats_handler_respects_admin_gate():
    non_admin = FakeAiogramMessage(text="/oisha_stats", user_id=10)
    admin = FakeAiogramMessage(text="/oisha_stats", user_id=11)

    async def _stats():
        return {"leads_found": 5, "messages_synced": 9}

    await handle_aiogram_oisha_stats(
        non_admin,
        is_admin=lambda _user_id: False,
        get_today_stats=_stats,
        cached_crm_audit={"health_score": 88},
    )
    await handle_aiogram_oisha_stats(
        admin,
        is_admin=lambda _user_id: True,
        get_today_stats=_stats,
        cached_crm_audit={"health_score": 88},
    )

    assert non_admin.answers == []
    assert "`5` ta" in admin.answers[0][0]
    assert "`88%`" in admin.answers[0][0]


@pytest.mark.asyncio
async def test_aiogram_sales_today_handler_respects_admin_gate():
    non_admin = FakeAiogramMessage(text="/sales_today", user_id=10)
    admin = FakeAiogramMessage(text="/sales_today", user_id=11)

    async def _priorities():
        return {
            "status": "ready",
            "items": [
                {
                    "lead_id": 7,
                    "name": "Hot lead",
                    "priority": "high",
                    "priority_score": 80,
                    "reasons": ["no_open_task"],
                    "action": "Call today.",
                }
            ],
            "scanned_count": 1,
            "skipped_closed_count": 0,
        }

    await handle_aiogram_sales_today(
        non_admin,
        is_admin=lambda _user_id: False,
        get_sales_today_priorities=_priorities,
    )
    await handle_aiogram_sales_today(
        admin,
        is_admin=lambda _user_id: True,
        get_sales_today_priorities=_priorities,
    )

    assert non_admin.answers == []
    assert "Hot lead #7" in admin.answers[0][0]


@pytest.mark.asyncio
async def test_aiogram_project_risks_handler_respects_admin_gate():
    non_admin = FakeAiogramMessage(text="/project_risks", user_id=10)
    admin = FakeAiogramMessage(text="/project_risks", user_id=11)

    async def _risks():
        return {
            "status": "ready",
            "items": [
                {
                    "project_id": "rec1",
                    "name": "Brandbook",
                    "risk": "critical",
                    "risk_score": 80,
                    "reasons": ["overdue"],
                    "action": "Fix deadline.",
                    "evidence": {"deadline": "2026-07-18", "manager": "Ali"},
                }
            ],
            "scanned_count": 1,
            "skipped_closed_count": 0,
        }

    await handle_aiogram_project_risks(
        non_admin,
        is_admin=lambda _user_id: False,
        get_project_delivery_risks=_risks,
    )
    await handle_aiogram_project_risks(
        admin,
        is_admin=lambda _user_id: True,
        get_project_delivery_risks=_risks,
    )

    assert non_admin.answers == []
    assert "Brandbook" in admin.answers[0][0]


@pytest.mark.asyncio
async def test_aiogram_finance_risks_handler_respects_admin_gate():
    non_admin = FakeAiogramMessage(text="/finance_risks", user_id=10)
    admin = FakeAiogramMessage(text="/finance_risks", user_id=11)

    async def _risks():
        return {
            "status": "ready",
            "items": [
                {
                    "project_id": "fin1",
                    "name": "Brandbook",
                    "risk": "critical",
                    "risk_score": 85,
                    "reasons": ["advance_below_50"],
                    "action": "Collect advance.",
                    "evidence": {
                        "budget": 20_000_000,
                        "paid_amount": 2_000_000,
                        "remaining_amount": 18_000_000,
                    },
                }
            ],
            "scanned_count": 1,
            "skipped_closed_count": 0,
        }

    await handle_aiogram_finance_risks(
        non_admin,
        is_admin=lambda _user_id: False,
        get_finance_project_risks=_risks,
    )
    await handle_aiogram_finance_risks(
        admin,
        is_admin=lambda _user_id: True,
        get_finance_project_risks=_risks,
    )

    assert non_admin.answers == []
    assert "Brandbook" in admin.answers[0][0]
    assert "50% avans" in admin.answers[0][0]


@pytest.mark.asyncio
async def test_aiogram_team_capacity_handler_respects_admin_gate():
    non_admin = FakeAiogramMessage(text="/team_capacity", user_id=10)
    admin = FakeAiogramMessage(text="/team_capacity", user_id=11)

    async def _capacity():
        return {
            "status": "ready",
            "items": [
                {
                    "owner_name": "Ali",
                    "load": "busy",
                    "load_score": 45,
                    "reasons": ["due_3_days"],
                    "action": "Confirm priorities.",
                    "evidence": {
                        "active_projects": 3,
                        "overdue_projects": 0,
                        "due_3_days": 2,
                    },
                }
            ],
            "scanned_count": 3,
            "unassigned_project_count": 0,
        }

    await handle_aiogram_team_capacity(
        non_admin,
        is_admin=lambda _user_id: False,
        get_team_capacity=_capacity,
    )
    await handle_aiogram_team_capacity(
        admin,
        is_admin=lambda _user_id: True,
        get_team_capacity=_capacity,
    )

    assert non_admin.answers == []
    assert "Ali" in admin.answers[0][0]
    assert "3 kun ichida deadline" in admin.answers[0][0]


@pytest.mark.asyncio
async def test_aiogram_command_center_handler_respects_admin_gate():
    non_admin = FakeAiogramMessage(text="/command_center", user_id=10)
    admin = FakeAiogramMessage(text="/command_center", user_id=11)

    async def _center():
        return {
            "status": "attention_required",
            "summary": {
                "attention_items": 1,
                "ready_sections": 1,
                "total_sections": 4,
                "unavailable_sections": ["finance"],
            },
            "sections": {
                "sales": {
                    "status": "ready",
                    "items": [{"name": "Hot lead", "priority": "high", "priority_score": 80}],
                }
            },
        }

    await handle_aiogram_command_center(
        non_admin,
        is_admin=lambda _user_id: False,
        get_command_center=_center,
    )
    await handle_aiogram_command_center(
        admin,
        is_admin=lambda _user_id: True,
        get_command_center=_center,
    )

    assert non_admin.answers == []
    assert "Oisha Command Center" in admin.answers[0][0]
    assert "Hot lead" in admin.answers[0][0]


def test_build_admin_aiogram_dispatcher_returns_dispatcher():
    async def _stats():
        return {}

    dispatcher = build_admin_aiogram_dispatcher(
        owner_id=1,
        get_role=lambda _user_id: None,
        get_role_name=lambda role: role,
        is_admin=lambda _user_id: True,
        get_today_stats=_stats,
        cached_crm_audit={},
    )

    assert dispatcher is not None


def test_maybe_build_admin_aiogram_dispatcher_is_default_off():
    async def _stats():
        return {}

    assert maybe_build_admin_aiogram_dispatcher(
        enabled=False,
        owner_id=1,
        get_role=lambda _user_id: None,
        get_role_name=lambda role: role,
        is_admin=lambda _user_id: True,
        get_today_stats=_stats,
        cached_crm_audit={},
    ) is None


def test_maybe_build_admin_aiogram_dispatcher_builds_when_enabled():
    async def _stats():
        return {}

    dispatcher = maybe_build_admin_aiogram_dispatcher(
        enabled=True,
        owner_id=1,
        get_role=lambda _user_id: None,
        get_role_name=lambda role: role,
        is_admin=lambda _user_id: True,
        get_today_stats=_stats,
        cached_crm_audit={},
    )

    assert dispatcher is not None


def test_boot_prepares_dispatcher_without_polling_or_webhook():
    text = open("src/boot.py", encoding="utf-8").read()

    assert "maybe_build_admin_aiogram_dispatcher" in text
    assert "TELEGRAM_ADMIN_AIOGRAM_DISPATCHER_ENABLED" in text
    assert "OISHA_COMMAND_CENTER_DIGEST_ENABLED" in text
    assert "app_ctx.admin_aiogram_dispatcher" in text
    assert "get_sales_today_priorities" in text
    assert "get_project_delivery_risks" in text
    assert "get_finance_project_risks" in text
    assert "get_team_capacity" in text
    assert "get_command_center" in text
    assert ".start_polling(" not in text


@pytest.mark.asyncio
async def test_aiogram_vps_status_handler():
    from src.services.core.admin_aiogram_dispatcher import handle_aiogram_vps_status

    non_admin = FakeAiogramMessage(text="/vps_status", user_id=10)
    admin = FakeAiogramMessage(text="/vps_status", user_id=11)

    await handle_aiogram_vps_status(non_admin, is_admin=lambda _uid: False)
    await handle_aiogram_vps_status(admin, is_admin=lambda _uid: True)

    assert non_admin.answers == []
    assert "TIZIM HOLATI" in admin.answers[0][0]
    assert "CPU:" in admin.answers[0][0]


class FakeDb:
    def __init__(self):
        self.state = {}

    async def get_state(self, key):
        return self.state.get(key)

    async def set_state(self, key, value):
        self.state[key] = str(value)


@pytest.mark.asyncio
async def test_aiogram_auto_status_and_control_handlers():
    from src.services.core.admin_aiogram_dispatcher import (
        handle_aiogram_auto_status,
        handle_aiogram_pause_auto,
        handle_aiogram_resume_auto,
        handle_aiogram_set_mode,
    )

    db = FakeDb()
    admin = FakeAiogramMessage(text="/auto_status", user_id=11)

    await handle_aiogram_auto_status(admin, is_admin=lambda _uid: True, db=db)
    assert "AUTO-REPLY STATUS" in admin.answers[0][0]

    pause_msg = FakeAiogramMessage(text="/pause_auto", user_id=11)
    await handle_aiogram_pause_auto(pause_msg, is_admin=lambda _uid: True, db=db)
    assert "Auto-reply PAUSED" in pause_msg.answers[0][0]
    assert db.state.get("auto_reply_live") == "false"

    resume_msg = FakeAiogramMessage(text="/resume_auto", user_id=11)
    await handle_aiogram_resume_auto(resume_msg, is_admin=lambda _uid: True, db=db)
    assert "Auto-reply RESUMED" in resume_msg.answers[0][0]
    assert db.state.get("auto_reply_live") == "true"

    mode_msg = FakeAiogramMessage(text="/set_mode shadow", user_id=11)
    await handle_aiogram_set_mode(mode_msg, is_admin=lambda _uid: True, db=db)
    assert "shadow" in mode_msg.answers[0][0]
    assert db.state.get("auto_reply_mode") == "shadow"


@pytest.mark.asyncio
async def test_aiogram_crm_report_handlers(monkeypatch):
    from src.services.core.admin_aiogram_dispatcher import (
        handle_aiogram_crm_report,
        handle_aiogram_crm_stats,
        handle_aiogram_crm_history,
    )

    class FakeStats:
        date_label = "Aug 17, 2026"
        total_leads = 8
        contacted = 5
        qualified = 4
        won = 2
        revenue = 2500
        pipeline_value = 15000

    class FakeReporter:
        def __init__(self, amocrm=None):
            pass
        async def fetch_stats(self):
            return FakeStats()
        def _load_prev_stats(self):
            return None
        def format_report(self, stats, prev):
            return f"AmoCRM Kunlik Hisobot | 📅 {stats.date_label}\nTushgan Leadlar: {stats.total_leads}\nSent via Oisha-OS"
        def get_history(self, days):
            return [FakeStats()]

    monkeypatch.setattr("src.services.core.crm.crm_daily_report.CRMDailyReporter", FakeReporter)

    admin = FakeAiogramMessage(text="/report", user_id=11)
    await handle_aiogram_crm_report(admin, is_admin=lambda _uid: True)
    assert len(admin.answers) == 2
    assert "AmoCRM Kunlik Hisobot" in admin.answers[1][0]
    assert "Tushgan Leadlar: 8" in admin.answers[1][0]

    stats_msg = FakeAiogramMessage(text="/stats", user_id=11)
    await handle_aiogram_crm_stats(stats_msg, is_admin=lambda _uid: True)
    assert len(stats_msg.answers) == 2
    assert "Bugungi holat" in stats_msg.answers[1][0]
    assert "Tushgan: 8 lead" in stats_msg.answers[1][0]

    hist_msg = FakeAiogramMessage(text="/history", user_id=11)
    await handle_aiogram_crm_history(hist_msg, is_admin=lambda _uid: True)
    assert len(hist_msg.answers) == 1
    assert "So'nggi 7 kunlik hisobotlar tarixi" in hist_msg.answers[0][0]



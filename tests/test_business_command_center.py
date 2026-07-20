from datetime import datetime, timezone

import pytest

from src.services.core.business_command_center import (
    branding_erp_roadmap,
    build_finance_project_risks,
    build_project_delivery_risks,
    build_sales_today_priorities,
    build_team_capacity_snapshot,
    collect_business_command_snapshot,
    list_integration_capabilities,
    plan_business_command,
    telegram_bot_migration_status,
)


def test_create_lead_requires_approval_and_extracts_phone():
    plan = plan_business_command(
        "Oltin Savdo kompaniyasiga lead yarat +998901234567"
    )

    assert plan.intent == "create_lead"
    assert plan.approval_required is True
    assert plan.entities["phone"] == "+998901234567"
    assert plan.required_sources == ("amocrm",)


def test_project_status_query_is_read_only_and_evidence_first():
    plan = plan_business_command("Oltin Savdo loyihasi qaysi bosqichda, deadline qachon?")

    assert plan.intent == "project_status_query"
    assert plan.mutation is False
    assert plan.approval_required is False
    assert plan.next_action == "read_live_project_status_with_deadline"


def test_reminder_extracts_time_and_requires_approval():
    plan = plan_business_command(
        "Ertaga soat 9 da yetkazib beruvchiga qo'ng'iroq qilishni eslat"
    )

    assert plan.intent == "create_reminder"
    assert plan.entities["time"] == "09:00"
    assert plan.approval_required is True


def test_idempotency_key_is_stable_for_normalized_command():
    first = plan_business_command("  LOYIHA HOLATI   qanday? ")
    second = plan_business_command("loyiha holati qanday?")

    assert first.idempotency_key == second.idempotency_key


def test_brief_or_proposal_requires_approval():
    plan = plan_business_command("Oltin Savdo uchun brief va KP tayyorla")

    assert plan.intent == "client_document_workflow"
    assert plan.approval_required is True
    assert plan.required_sources == ("amocrm", "google_workspace")


def test_payment_and_capacity_queries_are_service_business_focused():
    payment = plan_business_command("Qaysi mijozlardan avans kelmagan?")
    capacity = plan_business_command("Jamoa yuklamasi va bandlik qanday?")

    assert payment.intent == "payment_status_query"
    assert capacity.intent == "team_capacity_query"
    assert payment.approval_required is False
    assert capacity.approval_required is False


def test_unknown_command_requests_clarification():
    plan = plan_business_command("Shuni qilib qo'y")

    assert plan.intent == "clarification_required"
    assert plan.confidence < 0.5


def test_integration_registry_never_returns_secret_values(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "super-secret-token")
    monkeypatch.setenv("USERBOT_RUNTIME_OWNER", "disabled_local")

    payload = list_integration_capabilities()
    serialized = repr(payload)

    assert "super-secret-token" not in serialized
    bot = next(item for item in payload if item["key"] == "telegram_bot")
    userbot = next(item for item in payload if item["key"] == "telegram_userbot")
    assert bot["configured"] is True
    assert userbot["configured"] is False


def test_empty_command_is_rejected():
    with pytest.raises(ValueError, match="must not be empty"):
        plan_business_command("   ")


def test_branding_erp_roadmap_is_integration_first_and_server_based():
    roadmap = branding_erp_roadmap()
    serialized = repr(roadmap).lower()

    assert len(roadmap) >= 5
    assert "branding agencies" not in serialized  # title stays concise; API owns positioning
    assert "oracle vm" in serialized
    assert "amocrm" in serialized
    assert "google drive" in serialized
    assert "24/7" in serialized
    assert "userbot stays telethon" in serialized
    assert "aiogram" in serialized
    assert "not guessed" in serialized


def test_telegram_bot_migration_status_is_safe_and_rollbackable(monkeypatch):
    monkeypatch.setenv("USERBOT_RUNTIME_OWNER", "oracle_vm")
    monkeypatch.setenv("USERBOT_SESSION_STRING", "secret-userbot-session")
    monkeypatch.setenv("BOT_TOKEN", "secret-bot-token")

    status = telegram_bot_migration_status(
        bot_runtime_backend="aiogram",
        aiogram_dispatcher_enabled=False,
    )
    serialized = repr(status)

    assert "secret-userbot-session" not in serialized
    assert "secret-bot-token" not in serialized
    assert status["stage"] == "aiogram_send_only"
    assert status["userbot_runtime"] == "telethon_oracle_only"
    assert status["rollback_backend"] == "telethon"
    assert status["ready_count"] == status["total_count"]
    assert any("Oracle VM" in item["detail"] for item in status["checks"])


def test_telegram_bot_migration_status_flags_unsafe_dispatcher_order(monkeypatch):
    monkeypatch.setenv("USERBOT_RUNTIME_OWNER", "oracle_vm")
    monkeypatch.setenv("USERBOT_SESSION_STRING", "present")
    monkeypatch.setenv("BOT_TOKEN", "present")

    status = telegram_bot_migration_status(
        bot_runtime_backend="telethon",
        aiogram_dispatcher_enabled=True,
    )
    check = next(item for item in status["checks"] if item["key"] == "aiogram_dispatcher_safe")

    assert status["stage"] == "telethon_adapter_ready"
    assert check["ok"] is False


def test_sales_today_priorities_rank_open_actionable_leads():
    now = datetime.fromtimestamp(1_700_000_000, tz=timezone.utc)
    stale_ts = int(now.timestamp()) - 72 * 3600
    fresh_ts = int(now.timestamp()) - 2 * 3600
    leads = [
        {
            "id": 10,
            "name": "Closed deal",
            "status_id": 142,
            "updated_at": stale_ts,
        },
        {
            "id": 7,
            "name": "No task high value",
            "status_id": 123,
            "responsible_user_id": None,
            "price": 30_000_000,
            "updated_at": stale_ts,
            "_embedded": {"contacts": [{"id": 1}]},
        },
        {
            "id": 8,
            "name": "Fresh with task",
            "status_id": 124,
            "responsible_user_id": 99,
            "price": 1_000_000,
            "created_at": fresh_ts,
            "updated_at": fresh_ts,
            "_embedded": {"contacts": [{"id": 2}]},
        },
    ]

    result = build_sales_today_priorities(
        leads,
        open_tasks_by_lead={8: [{"complete_till": int(now.timestamp()) + 3600}]},
        now=now,
        limit=5,
    )

    assert result["status"] == "ready"
    assert result["skipped_closed_count"] == 1
    assert result["items"][0]["lead_id"] == 7
    assert result["items"][0]["priority"] == "high"
    assert "no_open_task" in result["items"][0]["reasons"]
    assert "stale_48h_plus" in result["items"][0]["reasons"]
    assert all(item["lead_id"] != 10 for item in result["items"])
    assert result["claim_policy"].startswith("Only AmoCRM")


def test_project_delivery_risks_rank_deadline_and_owner_gaps():
    result = build_project_delivery_risks(
        [
            {
                "id": "rec_done",
                "fields": {
                    "Project Name": "Done project",
                    "Stage": "Done",
                    "Deadline": "2026-07-01",
                },
            },
            {
                "id": "rec_overdue",
                "fields": {
                    "Project Name": "Brandbook",
                    "Stage": "Design",
                    "Deadline": "2026-07-18",
                    "Manager": "",
                },
            },
            {
                "id": "rec_missing",
                "fields": {
                    "Project Name": "Landing",
                    "Stage": "",
                    "Deadline": "",
                    "Manager": "Ali",
                },
            },
        ],
        today=datetime(2026, 7, 21, tzinfo=timezone.utc).date(),
    )

    assert result["status"] == "ready"
    assert result["skipped_closed_count"] == 1
    assert result["items"][0]["project_id"] == "rec_overdue"
    assert result["items"][0]["risk"] == "critical"
    assert "overdue" in result["items"][0]["reasons"]
    assert "owner_missing" in result["items"][0]["reasons"]
    assert all(item["project_id"] != "rec_done" for item in result["items"])
    assert "invented" in result["claim_policy"]


def test_finance_project_risks_rank_advance_and_missing_payment_fields():
    result = build_finance_project_risks(
        [
            {
                "id": "rec_done",
                "fields": {
                    "Project Name": "Done project",
                    "Stage": "Completed",
                    "Budget": "10000000",
                    "To'langan": "10000000",
                },
            },
            {
                "id": "rec_low_advance",
                "fields": {
                    "Project Name": "Brandbook",
                    "Stage": "Design",
                    "Budget": "20000000",
                    "To'langan": "3000000",
                    "To'lov statusi": "qarz",
                },
            },
            {
                "id": "rec_missing",
                "fields": {
                    "Project Name": "Landing",
                    "Stage": "Brief",
                },
            },
        ]
    )

    assert result["status"] == "ready"
    assert result["skipped_closed_count"] == 1
    assert result["items"][0]["project_id"] == "rec_low_advance"
    assert result["items"][0]["risk"] == "critical"
    assert "advance_below_50" in result["items"][0]["reasons"]
    assert "payment_overdue" in result["items"][0]["reasons"]
    assert result["items"][0]["evidence"]["margin"] is None
    assert "margin is not guessed" in result["claim_policy"]


def test_team_capacity_snapshot_ranks_busy_and_unassigned_projects():
    result = build_team_capacity_snapshot(
        [
            {
                "id": "done",
                "fields": {
                    "Project Name": "Done",
                    "Stage": "Completed",
                    "Manager": "Ali",
                },
            },
            {
                "id": "p1",
                "fields": {
                    "Project Name": "Brandbook",
                    "Stage": "Design",
                    "Manager": "Ali",
                    "Deadline": "2026-07-18",
                },
            },
            {
                "id": "p2",
                "fields": {
                    "Project Name": "Landing",
                    "Stage": "Brief",
                    "Manager": "Ali",
                    "Deadline": "2026-07-22",
                },
            },
            {
                "id": "p3",
                "fields": {
                    "Project Name": "Naming",
                    "Stage": "",
                    "Manager": "",
                    "Deadline": "",
                },
            },
        ],
        today=datetime(2026, 7, 21, tzinfo=timezone.utc).date(),
    )

    assert result["status"] == "ready"
    assert result["skipped_closed_count"] == 1
    assert result["unassigned_project_count"] == 1
    assert result["items"][0]["owner_name"] == "Ali"
    assert "overdue_projects" in result["items"][0]["reasons"]
    assert "due_3_days" in result["items"][0]["reasons"]
    assert "team capacity is not guessed" in result["claim_policy"]


@pytest.mark.asyncio
async def test_business_command_snapshot_preserves_unavailable_sections():
    snapshot = await collect_business_command_snapshot(
        amocrm=None,
        project_source=None,
        finance_source=None,
        hr_source=None,
        limit=2,
    )

    assert snapshot["status"] == "partial"
    assert snapshot["summary"]["total_sections"] == 4
    assert set(snapshot["summary"]["unavailable_sections"]) == {
        "sales",
        "projects",
        "finance",
        "team",
    }
    assert "guesses" in snapshot["claim_policy"]

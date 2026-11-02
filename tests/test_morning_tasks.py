"""Tests for Morning Task Triage & Secure Daily Review Engine."""
from datetime import datetime, timezone, timedelta
import pytest

from src.services.command_center.morning_tasks import (
    MorningTaskItem,
    MorningTriageService,
    TriageActionResult,
)


def test_morning_task_triage_grouping():
    now = datetime(2026, 11, 2, 8, 30, tzinfo=timezone.utc)
    tasks = [
        MorningTaskItem(
            task_id="t1",
            lead_id="l1",
            lead_name="Artel",
            text="Qayta qoʻngʻiroq qilish",
            due_date=now.date(),
            manager_id="mgr_1",
        ),
        MorningTaskItem(
            task_id="t2",
            lead_id="l2",
            lead_name="Akfa",
            text="Tijoriy taklif holatini bilish",
            due_date=(now - timedelta(days=2)).date(),
            manager_id="mgr_1",
        ),
    ]

    service = MorningTriageService(current_date=now.date())
    overview = service.get_overview(tasks)

    assert overview.today_count == 1
    assert overview.overdue_count == 1
    assert len(overview.today_tasks) == 1
    assert len(overview.overdue_tasks) == 1
    assert overview.today_tasks[0].task_id == "t1"
    assert overview.overdue_tasks[0].task_id == "t2"


def test_morning_task_bulk_actions():
    now = datetime(2026, 11, 2, 8, 30, tzinfo=timezone.utc)
    tasks = [
        MorningTaskItem(
            task_id="t1",
            lead_id="l1",
            lead_name="Artel",
            text="Suhbat",
            due_date=now.date(),
            manager_id="mgr_1",
        ),
        MorningTaskItem(
            task_id="t2",
            lead_id="l2",
            lead_name="Akfa",
            text="Taklif",
            due_date=now.date(),
            manager_id="mgr_1",
        ),
    ]

    service = MorningTriageService(current_date=now.date())

    # Mark done
    res_done = service.apply_action(tasks, action="done", task_ids=["t1"])
    assert res_done.updated_count == 1
    assert tasks[0].status == "done"

    # Reschedule t2 by 3 days
    res_resched = service.apply_action(tasks, action="reschedule", task_ids=["t2"], reschedule_days=3)
    assert res_resched.updated_count == 1
    assert tasks[1].due_date == (now + timedelta(days=3)).date()


def test_secure_review_token_generation_and_validation():
    service = MorningTriageService(secret_salt="oisha_secure_test_key_123")
    token = service.create_secure_review_token(call_id="call_999", manager_id="mgr_admin", ttl_minutes=15)
    assert token is not None

    # Valid check
    is_valid, payload = service.validate_review_token(token)
    assert is_valid is True
    assert payload["call_id"] == "call_999"
    assert payload["manager_id"] == "mgr_admin"

    # Tampered token
    is_valid_bad, _ = service.validate_review_token(token + "_tampered")
    assert is_valid_bad is False

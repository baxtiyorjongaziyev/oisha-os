"""Synthetic regression cases: the task audit never writes to amoCRM."""
from copy import deepcopy

from scripts.amocrm_revenue_task_audit import audit_tasks, is_ai_task, normalized


def _task(task_id, text, *, lead=100, due=1, completed=False):
    return {
        "id": task_id,
        "text": text,
        "entity_type": "leads",
        "entity_id": lead,
        "complete_till": due,
        "is_completed": completed,
    }


def test_human_tasks_are_never_classified_as_cleanup_candidates():
    calls = []
    tasks = [_task(1, "Mijozga telefon qiling")]
    assert audit_tasks(tasks, lambda lead: calls.append(lead)) == []
    assert calls == []


def test_active_revenue_task_is_preserved():
    tasks = [_task(2, "Oisha smart: Mijozga KP yuborib kelishuvni yoping")]
    result = audit_tasks(tasks, lambda _: 88871066)
    assert [r["outcome"] for r in result] == ["keep_revenue"]


def test_won_deal_payment_collection_is_preserved():
    tasks = [_task(3, "Oisha-OS Keyingi Qadam: Yakuniy toʻlovni undirish")]
    result = audit_tasks(tasks, lambda _: 142)
    assert result[0]["outcome"] == "keep_collection"


def test_nonrevenue_ai_task_on_closed_deal_is_review_only():
    tasks = [_task(4, "Oisha audit: maʼlumotlarni tekshiring")]
    result = audit_tasks(tasks, lambda _: 143)
    assert result[0]["outcome"] == "review_closed_deal"


def test_unknown_deal_status_fails_closed():
    tasks = [_task(5, "Oisha smart: mijoz bilan bogʻlanish")]
    result = audit_tasks(tasks, lambda _: None)
    assert result[0]["outcome"] == "review_unknown_status"


def test_lookup_errors_fail_closed():
    def lookup(_):
        raise ConnectionError("test outage")

    result = audit_tasks([_task(6, "Oisha smart: telefon qiling")], lookup)
    assert result[0]["outcome"] == "review_unknown_status"


def test_unlinked_task_is_review_only():
    tasks = [_task(7, "Telegram suhbatidan: suhbatni koʻrib chiqing", lead=None)]
    result = audit_tasks(tasks, lambda _: 88871066)
    assert result[0]["outcome"] == "review_unlinked"


def test_active_task_without_revenue_signal_needs_review():
    tasks = [_task(8, "Oisha audit: texnik logni tekshiring")]
    result = audit_tasks(tasks, lambda _: 88871066)
    assert result[0]["outcome"] == "review_no_revenue_signal"


def test_exact_duplicate_is_reviewed_not_deleted():
    tasks = [
        _task(10, "Oisha smart: KP yuboring", lead=88, due=123),
        _task(11, "Oisha smart: KP yuboring", lead=88, due=123),
        _task(12, "Oisha smart: KP yuboring", lead=88, due=999),
    ]
    before = deepcopy(tasks)
    result = audit_tasks(tasks, lambda _: 88871066)
    assert {r["task_id"]: r["outcome"] for r in result} == {
        10: "review_duplicate",
        11: "keep_revenue",
        12: "keep_revenue",
    }
    assert tasks == before


def test_completed_ai_task_is_not_reported():
    tasks = [_task(13, "Oisha smart: KP yuboring", completed=True)]
    assert audit_tasks(tasks, lambda _: 88871066) == []


def test_oisha_markers_and_uzbek_apostrophes():
    assert is_ai_task(_task(14, "🤖 Oisha-OS Keyingi Qadam: qoʻngʻiroq qiling")) is False
    assert is_ai_task(_task(15, "Oisha-OS Keyingi Qadam: qoʻngʻiroq qiling"))
    assert normalized("Toʻlov") == normalized("To'lov")

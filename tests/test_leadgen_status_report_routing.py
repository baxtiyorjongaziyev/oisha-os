"""Regression: daily status report must go only to Marketing, never to the Target Leads topic."""
import asyncio
from types import SimpleNamespace
from unittest.mock import patch

from src.schedulers import leadgen_status_reporter as rep


def _run(send_result: bool):
    calls = []

    def fake_send(text, chat_id, topic_id=None, **kwargs):
        calls.append((chat_id, topic_id))
        return send_result

    with patch.object(rep, "get_creative_summary", return_value=[]), \
         patch.object(rep, "build_status_report_text", return_value="report"), \
         patch.object(rep, "build_creative_buttons", return_value=[]), \
         patch.object(rep, "_send_tg_message", side_effect=fake_send), \
         patch.object(rep, "settings", SimpleNamespace(
             MARKETING_REPORT_CHAT_ID=-100777,
             MARKETING_REPORT_TOPIC_ID=42,
             TARGET_LEADS_GROUP_ID=-100555,
             TARGET_LEADS_TOPIC_ID=1020,
         )):
        ok = asyncio.run(rep.send_daily_status_report())
    return ok, calls


def test_report_sent_only_to_marketing():
    ok, calls = _run(True)
    assert ok is True
    assert calls == [(-100777, 42)]


def test_report_never_hits_target_leads_topic():
    _, calls = _run(True)
    assert all(chat != -100555 and topic != 1020 for chat, topic in calls)


def test_failure_reflects_marketing_send_only():
    ok, calls = _run(False)
    assert ok is False
    assert len(calls) == 1

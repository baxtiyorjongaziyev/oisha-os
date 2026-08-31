from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import SecretStr

import src.schedulers.instagram_weekly_reporter as weekly_reporter
from src.services.core.instagram_weekly_report import InstagramWeeklyReportAgent


class _Agent(InstagramWeeklyReportAgent):
    async def _get_json(self, url, params):
        if url.endswith("/ig_1/media"):
            return {
                "data": [
                    {
                        "id": "m1",
                        "caption": "Yirik mijoz uchun branding case: jarayon va natija",
                        "media_product_type": "REELS",
                        "permalink": "https://instagram.com/p/1",
                        "timestamp": "2026-07-01T09:00:00+0000",
                        "like_count": 50,
                        "comments_count": 7,
                    },
                    {
                        "id": "m2",
                        "caption": "Qimmat mashina bilan ofisdan lavha",
                        "media_type": "CAROUSEL_ALBUM",
                        "permalink": "https://instagram.com/p/2",
                        "timestamp": "2026-07-02T09:00:00+0000",
                        "like_count": 20,
                        "comments_count": 1,
                    },
                ]
            }
        if url.endswith("/m1/insights"):
            return {"data": [{"name": "reach", "values": [{"value": 1200}]}, {"name": "saved", "values": [{"value": 18}]}, {"name": "shares", "values": [{"value": 9}]}, {"name": "total_interactions", "values": [{"value": 84}]}]}
        if url.endswith("/m2/insights"):
            return {"data": [{"name": "reach", "values": [{"value": 800}]}, {"name": "saved", "values": [{"value": 1}]}, {"name": "shares", "values": [{"value": 0}]}, {"name": "total_interactions", "values": [{"value": 21}]}]}
        return {}


@pytest.mark.asyncio
async def test_fetch_and_grounded_report():
    settings = SimpleNamespace(
        META_INSTAGRAM_USER_ID="ig_1",
        META_PAGE_ACCESS_TOKEN=SecretStr("token"),
        OPENAI_API_KEY=None,
        AIRTABLE_BASE_ID=None,
        INSTAGRAM_REPORT_AIRTABLE_TABLE=None,
    )
    agent = _Agent(settings)

    posts = await agent.fetch_weekly_posts()
    report = await agent.build_report(posts)

    assert len(posts) == 2
    assert posts[0].reach == 1200
    assert posts[0].lead_score > posts[1].lead_score
    assert "qimmat tafakkur" in report


@pytest.mark.asyncio
async def test_missing_env_returns_safe_report_without_crash():
    settings = SimpleNamespace(
        META_INSTAGRAM_USER_ID=None,
        META_INSTAGRAM_ACCOUNT_ID=None,
        META_PAGE_ACCESS_TOKEN=None,
        OPENAI_API_KEY=None,
        AIRTABLE_BASE_ID=None,
        INSTAGRAM_REPORT_AIRTABLE_TABLE=None,
    )
    agent = InstagramWeeklyReportAgent(settings)

    result = await agent.run()

    assert result["posts"] == []
    assert "META_INSTAGRAM_USER_ID" in result["report"]
    assert "META_PAGE_ACCESS_TOKEN" in result["report"]


def test_safe_telegram_html_escapes_unknown_tags():
    agent = InstagramWeeklyReportAgent(SimpleNamespace())

    report = agent._safe_telegram_html("<b>OK</b><script>alert(1)</script><i>Italic</i>")

    assert "<b>OK</b>" in report
    assert "<i>Italic</i>" in report
    assert "<script>" not in report
    assert "&lt;script&gt;" in report


@pytest.mark.asyncio
async def test_send_instagram_weekly_report_uses_bot_client(monkeypatch):
    class _FakeAgent:
        async def run(self):
            return {"posts": [], "report": "📊 <b>Report</b>"}

    class _Bot:
        def __init__(self):
            self.sent = []

        async def send_message(self, chat_id, text, **kwargs):
            self.sent.append((chat_id, text, kwargs))

    monkeypatch.setattr(weekly_reporter, "InstagramWeeklyReportAgent", _FakeAgent)
    bot = _Bot()

    report = await weekly_reporter.send_instagram_weekly_report(
        bot_client=bot, team_group_id=-100123, topic_id=42
    )

    assert report == "📊 <b>Report</b>"
    assert bot.sent == [(-100123, "📊 <b>Report</b>", {"parse_mode": "html", "message_thread_id": 42})]



@pytest.mark.asyncio
async def test_instagram_weekly_report_loop_skips_unconfigured(monkeypatch):
    import asyncio
    from datetime import datetime
    from zoneinfo import ZoneInfo

    class _UnconfiguredAgent:
        def credential_status(self):
            return {"META_INSTAGRAM_USER_ID": False, "META_PAGE_ACCESS_TOKEN": False}

    class _Bot:
        def __init__(self):
            self.sent = []

        async def send_message(self, chat_id, text, **kwargs):
            self.sent.append((chat_id, text, kwargs))

    # Mock get_local_now to return Monday 09:30
    monday_930 = datetime(2026, 8, 31, 9, 30, 0, tzinfo=ZoneInfo("Asia/Tashkent"))
    monkeypatch.setattr("src.time_utils.get_local_now", lambda: monday_930)
    monkeypatch.setattr(weekly_reporter, "InstagramWeeklyReportAgent", _UnconfiguredAgent)

    # Short-circuit asyncio.sleep so loop doesn't hang
    sleep_calls = 0

    async def _mock_sleep(seconds):
        nonlocal sleep_calls
        sleep_calls += 1
        if sleep_calls >= 2:
            raise asyncio.CancelledError()

    monkeypatch.setattr(asyncio, "sleep", _mock_sleep)

    bot = _Bot()
    with pytest.raises(asyncio.CancelledError):
        await weekly_reporter.instagram_weekly_report_loop(bot, -100123)

    # Bot should NOT have sent any message since credentials were not configured
    assert bot.sent == []


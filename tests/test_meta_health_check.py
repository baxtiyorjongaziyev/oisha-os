from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import pytest

import src.schedulers.meta_health_scheduler as scheduler
from src.services.core.instagram.meta_health_check import (
    FAIL,
    OK,
    WARN,
    MetaHealthCheck,
    _peak_usage,
    format_report,
)

TOKEN = "EAAG-secret-token"
ALL_SCOPES = ["instagram_basic", "instagram_manage_messages", "instagram_manage_comments", "pages_show_list"]


def _client(page_id="123", version="v19.0", token=TOKEN):
    return SimpleNamespace(access_token=token, page_id=page_id, api_version=version)


def _fake_http(debug=None, subscribed=None, headers=None, calls=None):
    async def http_get(url, params, token):
        if calls is not None:
            calls.append((url, params, token))
        if url.endswith("/debug_token"):
            return debug if debug is not None else (200, {"data": {
                "is_valid": True, "app_id": "999", "expires_at": 0, "scopes": ALL_SCOPES,
            }}, headers or {"facebook-api-version": "v19.0"})
        if url.endswith("/subscribed_apps"):
            return subscribed if subscribed is not None else (200, {"data": [
                {"id": "999", "name": "Oisha", "subscribed_fields": ["messages", "feed"]},
            ]}, {})
        raise AssertionError(url)
    return http_get


def _by_title(findings):
    return {f.title: f for f in findings}


@pytest.mark.asyncio
async def test_healthy_app_reports_all_ok_and_uses_bearer_header():
    calls = []
    findings = await MetaHealthCheck(_client(), _fake_http(calls=calls)).run()
    assert {f.level for f in findings} == {OK}
    assert "messages" in _by_title(findings)["Webhook"].detail
    debug_url, debug_params, token = calls[0]
    assert debug_url == "https://graph.facebook.com/v19.0/debug_token"
    assert token == TOKEN
    assert "access_token" not in debug_params


@pytest.mark.asyncio
async def test_missing_token_fails_without_network():
    findings = await MetaHealthCheck(_client(token=""), _fake_http()).run()
    assert findings[0].level == FAIL and "META_PAGE_ACCESS_TOKEN" in findings[0].detail


@pytest.mark.asyncio
async def test_invalid_token_and_missing_scopes():
    debug = (200, {"data": {"is_valid": False, "error": {"message": "Session expired"}}}, {})
    findings = _by_title(await MetaHealthCheck(_client(), _fake_http(debug=debug)).run())
    assert findings["Token"].level == FAIL and "Session expired" in findings["Token"].detail

    debug = (200, {"data": {"is_valid": True, "app_id": "999", "scopes": ["instagram_basic"]}}, {})
    findings = _by_title(await MetaHealthCheck(_client(), _fake_http(debug=debug)).run())
    assert findings["Ruxsatlar"].level == FAIL
    assert "instagram_manage_messages" in findings["Ruxsatlar"].detail


def test_token_expiry_warning():
    now = datetime(2026, 10, 5, tzinfo=timezone.utc)
    soon = int((now + timedelta(days=5)).timestamp())
    later = int((now + timedelta(days=40)).timestamp())
    assert MetaHealthCheck._expiry_finding({"expires_at": soon}, now).level == WARN
    assert MetaHealthCheck._expiry_finding({"expires_at": later}, now).level == OK


@pytest.mark.asyncio
async def test_auto_upgraded_api_version_is_flagged():
    headers = {"facebook-api-version": "v21.0"}
    findings = _by_title(await MetaHealthCheck(_client(), _fake_http(headers=headers)).run())
    assert findings["API versiya"].level == WARN
    assert "v19.0" in findings["API versiya"].detail and "v21.0" in findings["API versiya"].detail


@pytest.mark.asyncio
async def test_high_rate_limit_usage_warns():
    headers = {
        "facebook-api-version": "v19.0",
        "x-business-use-case-usage": json.dumps({"123": [{"type": "pages", "call_count": 82, "total_time": 10}]}),
    }
    findings = _by_title(await MetaHealthCheck(_client(), _fake_http(headers=headers)).run())
    assert findings["Rate limit"].level == WARN and "82%" in findings["Rate limit"].detail


def test_peak_usage_parsing():
    assert _peak_usage('{"call_count": 12, "total_cputime": 40, "total_time": 7}') == 40
    assert _peak_usage("not json") == 0
    assert _peak_usage(None) == 0


@pytest.mark.asyncio
async def test_webhook_problems():
    unsubscribed = (200, {"data": [{"id": "111", "subscribed_fields": ["feed"]}]}, {})
    findings = _by_title(await MetaHealthCheck(_client(), _fake_http(subscribed=unsubscribed)).run())
    assert findings["Webhook"].level == FAIL

    no_page = _by_title(await MetaHealthCheck(_client(page_id=""), _fake_http()).run())
    assert no_page["Webhook"].level == WARN


@pytest.mark.asyncio
async def test_network_error_is_reported_not_raised():
    async def boom(url, params, token):
        raise httpx.ConnectError("down")

    findings = _by_title(await MetaHealthCheck(_client(page_id=""), boom).run())
    assert findings["Graph API"].level == FAIL


def test_report_never_contains_token_and_escapes_html():
    from src.services.core.instagram.meta_health_check import HealthFinding

    report = format_report([HealthFinding(FAIL, "Token", "Yaroqsiz: <b>bad</b>")])
    assert "muammo bor" in report and "&lt;b&gt;bad&lt;/b&gt;" in report
    assert TOKEN not in report


@pytest.mark.asyncio
async def test_send_report_goes_to_owner(monkeypatch):
    sent = []

    class _Bot:
        async def send_message(self, chat_id, text, **kwargs):
            sent.append((chat_id, text, kwargs))

    class _Check:
        async def run(self):
            from src.services.core.instagram.meta_health_check import HealthFinding
            return [HealthFinding(OK, "Token", "Amal qiladi")]

    monkeypatch.setattr(scheduler, "MetaHealthCheck", _Check)
    monkeypatch.setattr("src.settings.settings.OWNER_ID", 42, raising=False)
    report = await scheduler.send_meta_health_report(bot_client=_Bot())
    assert sent and sent[0][0] == 42 and sent[0][2] == {"parse_mode": "html"}
    assert "hammasi joyida" in report


def test_enabled_flag(monkeypatch):
    monkeypatch.setenv("META_HEALTH_CHECK_ENABLED", "0")
    assert scheduler._enabled() is False
    monkeypatch.delenv("META_HEALTH_CHECK_ENABLED")
    assert scheduler._enabled() is True

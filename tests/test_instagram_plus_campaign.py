"""scripts/instagram_plus_campaign — rejalashtirish va yuborish mantiqi."""
from datetime import datetime, timedelta, timezone

from scripts.instagram_plus_campaign import (
    CONFIRM_TEXT,
    PUBLIC_INVITE_TEXT,
    execute,
    main,
    plan_actions,
)
from src.services.core.instagram.agent_constants import (
    KEYWORD_AUTOMATION_PUBLIC_ACK,
    is_plus_only_comment,
)

NOW = datetime(2026, 10, 6, 12, tzinfo=timezone.utc)
OWN = "own_ig"


def _c(cid, text, days_ago, author="u1", replies=None):
    ts = (NOW - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%S%z")
    return {"id": cid, "text": text, "timestamp": ts, "from": {"id": author},
            "replies": {"data": replies or []}}


def _plan(comments):
    return plan_actions(comments, OWN, NOW, NOW - timedelta(days=60),
                        [KEYWORD_AUTOMATION_PUBLIC_ACK, PUBLIC_INVITE_TEXT], is_plus_only_comment)


def test_plan_splits_by_meta_private_reply_window():
    plan = _plan([_c("a", "+", 2), _c("b", "++", 20), _c("c", "+", 90)])
    assert plan == [{"comment_id": "a", "action": "dm"}, {"comment_id": "b", "action": "invite"}]


def test_plan_skips_non_plus_own_and_duplicates():
    plan = _plan([_c("a", "+998 90 1234567", 1), _c("b", "+", 1, author=OWN),
                  _c("c", "+", 1), _c("c", "+", 1)])
    assert [p["comment_id"] for p in plan] == ["c"]


def test_plan_skips_comments_already_handled_by_campaign_or_webhook():
    ack = {"from": {"id": OWN}, "text": KEYWORD_AUTOMATION_PUBLIC_ACK}
    other_ai_reply = {"from": {"id": OWN}, "text": "Rahmat! ✨"}
    plan = _plan([_c("a", "+", 1, replies=[ack]), _c("b", "+", 1, replies=[other_ai_reply])])
    assert [p["comment_id"] for p in plan] == ["b"]


def test_execute_sends_dm_with_ack_and_invite_publicly():
    calls = []
    send_dm = lambda cid, text, tok: calls.append(("dm", cid)) or cid != "bad"
    reply = lambda cid, text, tok: calls.append(("reply", cid, text)) or True
    plan = [{"comment_id": "a", "action": "dm"}, {"comment_id": "b", "action": "invite"},
            {"comment_id": "bad", "action": "dm"}]

    stats = execute(plan, "tok", send_dm, reply, "DM", "ACK", throttle=0)

    assert stats == {"dm_sent": 1, "invite_sent": 1, "failed": 1}
    assert ("reply", "a", "ACK") in calls
    assert ("reply", "b", PUBLIC_INVITE_TEXT) in calls
    assert not any(c[0] == "reply" and c[1] == "bad" for c in calls)


def test_live_requires_confirm(monkeypatch):
    monkeypatch.setattr("scripts.instagram_plus_campaign._load_env", lambda: None)
    monkeypatch.setenv("META_PAGE_ACCESS_TOKEN", "t")
    monkeypatch.setenv("META_INSTAGRAM_USER_ID", OWN)
    assert main(["--live"]) == 2
    assert CONFIRM_TEXT == "YUBORISH"


class _Resp:
    def __init__(self, body, status=200):
        self._body, self.status_code = body, status

    def json(self):
        return self._body


def test_check_token_reports_ads_read_and_accounts(monkeypatch):
    from scripts import instagram_plus_campaign as mod

    def fake_get(url, params=None, timeout=None):
        if url.endswith("/debug_token"):
            return _Resp({"data": {"is_valid": True, "type": "PAGE",
                                   "scopes": ["instagram_basic", "ads_read"]}})
        return _Resp({"data": [{"id": "act_1", "name": "Jon"}]})

    monkeypatch.setattr(mod.requests, "get", fake_get)
    info = mod.check_token("tok")
    assert info["valid"] and info["ads_read"]
    assert info["ad_accounts"] == [{"id": "act_1", "name": "Jon"}]


def test_check_token_without_ads_read(monkeypatch):
    from scripts import instagram_plus_campaign as mod

    def fake_get(url, params=None, timeout=None):
        if url.endswith("/debug_token"):
            return _Resp({"data": {"is_valid": True, "scopes": ["instagram_basic"]}})
        return _Resp({"error": {"message": "no permission"}}, status=400)

    monkeypatch.setattr(mod.requests, "get", fake_get)
    info = mod.check_token("tok")
    assert info["ads_read"] is False
    assert info["ad_accounts"] == []
    assert any("adaccounts" in e for e in info["errors"])


def test_discover_ad_accounts_via_page_business(monkeypatch):
    from scripts import instagram_plus_campaign as mod

    def fake_get(url, params=None, timeout=None):
        if url.endswith("/me") and params.get("fields") == "business":
            return _Resp({"business": {"id": "biz1"}})
        if url.endswith("/me") or url.endswith("/me/adaccounts"):
            return _Resp({"error": {"message": "nonexisting field"}}, status=400)
        if url.endswith("/biz1/owned_ad_accounts"):
            return _Resp({"data": [{"id": "act_9", "name": "Jon Ads"}]})
        if url.endswith("/biz1/client_ad_accounts"):
            return _Resp({"data": [{"id": "act_9", "name": "Jon Ads"}]})
        raise AssertionError(url)

    monkeypatch.setattr(mod.requests, "get", fake_get)
    errors = []
    assert mod.discover_ad_accounts("tok", errors) == [{"id": "act_9", "name": "Jon Ads"}]
    assert any("adaccounts" in e for e in errors)

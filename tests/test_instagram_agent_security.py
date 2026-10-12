"""Instagram bot: CRM HTML injection, unsafe public AI replies, per-user rate limit."""
from unittest.mock import patch

from src.services.core import instagram_agent as ia


def test_notify_crm_escapes_user_controlled_html(monkeypatch):
    monkeypatch.setattr(ia.settings, "CRM_GROUP_ID", -100, raising=False)
    monkeypatch.setattr(ia.settings, "CRM_TOPIC_ID", None, raising=False)
    monkeypatch.setattr(ia.settings, "BOT_TOKEN", type("S", (), {"get_secret_value": lambda self: "t"})(), raising=False)
    with patch.object(ia.requests, "post") as post:
        post.return_value.status_code = 200
        ia.notify_crm(
            "Instagram Comment",
            '<a href="https://evil">Admin</a>',
            "1",
            "I <3 you <b>",
            "javob",
        )
    text = post.call_args.kwargs["json"]["text"]
    assert '<a href="https://evil">' not in text
    assert "&lt;a href=" in text and "I &lt;3 you &lt;b&gt;" in text


def test_is_safe_public_reply_blocks_links_mentions_phones():
    assert ia.is_safe_public_reply("Rahmat! Batafsil bio'da 🙌")
    for bad in (
        "Ko'ring: https://evil.example",
        "t.me/scam ga yozing",
        "Saytimiz evil.com",
        "@scammer ga yozing",
        "Qo'ng'iroq: +998 90 123 45 67",
        "x" * 401,
        "",
    ):
        assert not ia.is_safe_public_reply(bad), bad


def test_allow_auto_reply_rate_limits_per_commenter():
    ia._auto_reply_log.clear()
    assert all(ia.allow_auto_reply("u1", now=1000 + i) for i in range(3))
    assert not ia.allow_auto_reply("u1", now=1010)
    assert ia.allow_auto_reply("u2", now=1010)
    assert ia.allow_auto_reply("u1", now=1000 + 3601)

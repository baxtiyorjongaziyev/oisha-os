"""Lid manbasi: 7 toifa, ustuvorlik va telefon xeshi bo'yicha bog'lash."""
from __future__ import annotations

import pytest

from src.services.core.leads import lead_source as ls


@pytest.mark.parametrize("tracking,kw,expected", [
    ({"fbclid": "x", "referrer": "https://google.com/"}, {}, ls.AD),
    ({"utm_source": "instagram", "utm_medium": "paid"}, {}, ls.AD),
    ({"utm_source": "telegram", "utm_medium": "cpc"}, {}, ls.AD),
    ({}, {"leadgen": True}, ls.AD),
    ({"referrer": "https://www.google.com/search?q=x"}, {}, ls.SEARCH),
    ({"referrer": "https://yandex.uz/"}, {}, ls.SEARCH),
    ({"referrer": "https://l.facebook.com/"}, {}, ls.FB),
    ({"referrer": "https://l.instagram.com/"}, {}, ls.IG),
    ({"utm_source": "instagram", "utm_medium": "bio"}, {}, ls.IG),
    ({"page_url": "https://jonbranding.uz/"}, {}, ls.SITE),
    ({}, {"incoming_call": True}, ls.CALL),
    ({}, {}, ls.UNKNOWN),
])
def test_classify(tracking, kw, expected):
    assert ls.classify(tracking, **kw) == expected


def test_incoming_call_uses_site_visit(monkeypatch, tmp_path):
    monkeypatch.setattr(ls, "_DB_PATH", tmp_path / "v.db")
    assert ls.source_for_incoming_call("+998901234567") == ls.CALL
    ls.remember_visit("+998 90 123 45 67", {"fbclid": "abc", "page_url": "https://x"})
    assert ls.source_for_incoming_call("901234567") == ls.AD


def test_ad_visit_not_overwritten_by_organic(monkeypatch, tmp_path):
    monkeypatch.setattr(ls, "_DB_PATH", tmp_path / "v.db")
    ls.remember_visit("998901234567", {"fbclid": "abc"}, now=1000)
    ls.remember_visit("998901234567", {"page_url": "https://x"}, now=2000)
    assert ls.classify(ls.visit_for_phone("998901234567", now=2000)) == ls.AD


def test_visit_expires(monkeypatch, tmp_path):
    monkeypatch.setattr(ls, "_DB_PATH", tmp_path / "v.db")
    ls.remember_visit("998901234567", {"fbclid": "abc"}, now=1000)
    assert ls.visit_for_phone("998901234567", now=1000 + ls.VISIT_TTL_SEC + 1) is None


def test_phone_not_stored_in_plaintext(monkeypatch, tmp_path):
    monkeypatch.setattr(ls, "_DB_PATH", tmp_path / "v.db")
    ls.remember_visit("998901234567", {"fbclid": "abc"})
    assert b"901234567" not in (tmp_path / "v.db").read_bytes()

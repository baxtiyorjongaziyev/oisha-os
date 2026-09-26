import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest

from src.schedulers import leadgen_status_reporter as rep


def _ts(delta: timedelta) -> str:
    return (datetime.now(timezone.utc) - delta).strftime("%Y-%m-%d %H:%M:%S")


@pytest.fixture
def attribution_db(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE lead_attribution (leadgen_id TEXT, ad_id TEXT, created_at TEXT)")
    rows = [
        ("a1", "120249419742870032", _ts(timedelta(hours=1))),
        ("a2", "120249419742870032", _ts(timedelta(hours=2))),
        ("a3", "999", _ts(timedelta(hours=3))),
        ("old", "120249419742870032", _ts(timedelta(days=5))),
    ]
    conn.executemany("INSERT INTO lead_attribution VALUES (?, ?, ?)", rows)

    @contextmanager
    def fake_connection():
        yield conn

    import src.services.core.marketing.attribution_store as store

    monkeypatch.setattr(store, "_connection", fake_connection)

    class FakeClient:
        def get_ad_name(self, ad_id):
            return "Video 9 - Sentabr" if ad_id == "999" else None

        def get_ad_creative_url(self, ad_id):
            return "https://www.instagram.com/p/NEW/" if ad_id == "999" else None

    monkeypatch.setattr(rep, "_meta_client", lambda: FakeClient())
    rep._AD_NAME_CACHE.clear()
    rep._AD_URL_CACHE.clear()
    yield conn
    conn.close()


def test_summary_only_counts_last_24h(attribution_db):
    summary = rep.get_creative_summary()
    assert [(n, c) for n, c, _, _ in summary] == [("v2 (Video 2)", 2), ("Video 9 - Sentabr", 1)]
    assert sum(c for _, c, _, _ in summary) == 3


def test_all_time_window_includes_old(attribution_db):
    summary = rep.get_creative_summary(hours=24 * 30)
    assert summary[0][1] == 3


def test_buttons_match_summary_numbers(attribution_db):
    summary = rep.get_creative_summary()
    buttons = rep.build_creative_buttons(summary)
    texts = [row[0]["text"] for row in buttons]
    assert texts == [
        "🎬 v2 (Video 2) — 2 ta lid (66.7%)",
        "🎬 Video 9 - Sentabr — 1 ta lid (33.3%)",
    ]
    assert buttons[1][0]["url"] == "https://www.instagram.com/p/NEW/"


def test_ad_name_lookup_is_cached(attribution_db, monkeypatch):
    calls = []

    class CountingClient:
        def get_ad_name(self, ad_id):
            calls.append(ad_id)
            return None

    monkeypatch.setattr(rep, "_meta_client", lambda: CountingClient())
    assert rep._resolve_ad_name("555") == "Ad 555"
    assert rep._resolve_ad_name("555") == "Ad 555"
    assert calls == ["555"]

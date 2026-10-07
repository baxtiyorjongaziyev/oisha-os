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


def test_local_offset_timestamps_use_true_24h_window(attribution_db):
    # Router writes Tashkent ISO time with offset; 26h-old lead must not leak into the window.
    tz = timezone(timedelta(hours=5))
    attribution_db.executemany(
        "INSERT INTO lead_attribution VALUES (?, ?, ?)",
        [
            ("loc_new", "999", (datetime.now(tz) - timedelta(hours=1)).isoformat()),
            ("loc_old", "999", (datetime.now(tz) - timedelta(hours=26)).isoformat()),
        ],
    )
    summary = dict((n, c) for n, c, _, _ in rep.get_creative_summary())
    assert summary["Video 9 - Sentabr"] == 2


def test_meta_lines_flag_missing_and_api_failure():
    ok, total = rep._meta_lines((32, 0), 542)
    assert ok.startswith("• 🟢") and "32 ta" in ok
    assert "butun vaqt" in total and "542" in total
    short, _ = rep._meta_lines((40, 2), 542)
    assert short.startswith("• 🔴") and "2 ta AmoCRM'ga yetmagan" in short
    down_24h, down_total = rep._meta_lines(None, None)
    assert "javob bermadi" in down_24h and "javob bermadi" in down_total


def test_meta_24h_status_matches_by_lead_id(monkeypatch):
    from src.schedulers import leadgen_reconciliation as rec
    from src.schedulers import meta_leadgen_scheduler as m

    old = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2)
    monkeypatch.setattr(m, "_get_page_token", lambda: "tok")
    monkeypatch.setattr(rec, "_meta_leads", lambda since: [("L1", old), ("L2", old)])
    # An old retried lead ("OLD") in deliveries must not mask the missing L2.
    monkeypatch.setattr(rec, "_delivered_ids", lambda: ["L1", "OLD"])
    assert rep._meta_24h_status() == (2, 1)


def test_meta_24h_status_none_without_token(monkeypatch):
    from src.schedulers import meta_leadgen_scheduler as m

    monkeypatch.setattr(m, "_get_page_token", lambda: "")
    assert rep._meta_24h_status() is None

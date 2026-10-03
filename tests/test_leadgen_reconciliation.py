import asyncio
import datetime as dt

from src.schedulers import leadgen_reconciliation as rec

NOW = dt.datetime(2026, 10, 2, 12, 0)


def _ago(minutes):
    return NOW - dt.timedelta(minutes=minutes)


def test_find_missing_respects_grace_and_delivered():
    meta = [("a", _ago(120)), ("b", _ago(60)), ("c", _ago(10))]
    missing = rec.find_missing(meta, delivered_ids=["b"], now=NOW, grace_min=30)
    assert [lid for lid, _ in missing] == ["a"]  # c hali grace ichida, b yetkazilgan


def _run(monkeypatch, meta, delivered):
    sent = []
    monkeypatch.setattr(rec, "_meta_leads", lambda since: meta)
    monkeypatch.setattr(rec, "_delivered_ids", lambda: delivered)
    monkeypatch.setattr(
        "src.services.core.instagram.leadgen_watchdog.send_admin_alert",
        lambda text, technical=False: sent.append((text, technical)) or True,
    )
    n = asyncio.run(rec.reconcile_once(now=NOW))
    return n, sent


def test_alerts_once_then_recovery(monkeypatch):
    monkeypatch.setattr(rec, "_state", {"last_alert_at": 0.0, "last_missing": 0.0})
    meta = [("x", _ago(90)), ("y", _ago(45))]

    n, sent = _run(monkeypatch, meta, delivered=[])
    assert n == 2 and len(sent) == 1 and sent[0][1] is True
    assert "AMOCRM'GA YETMAYAPTI" in sent[0][0]

    n, sent = _run(monkeypatch, meta, delivered=[])  # o'zgarmadi -> takror alert yo'q
    assert n == 2 and sent == []

    n, sent = _run(monkeypatch, meta, delivered=["x", "y"])  # tiklandi
    assert n == 0 and len(sent) == 1 and "tiklandi" in sent[0][0]


def test_no_alert_when_all_delivered(monkeypatch):
    monkeypatch.setattr(rec, "_state", {"last_alert_at": 0.0, "last_missing": 0.0})
    n, sent = _run(monkeypatch, [("x", _ago(90))], delivered=["x"])
    assert n == 0 and sent == []

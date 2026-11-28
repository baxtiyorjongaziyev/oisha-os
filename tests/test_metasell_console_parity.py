"""Tests for Metasell Console Parity: Leaderboard, Micro-Checklist, and AI Sales Chat."""
from __future__ import annotations

import csv
import io
import json
import pytest


def _make_call_row(
    *,
    call_id: str,
    lead_id: int,
    manager_id: int,
    manager_name: str,
    overall_score: int,
    duration_seconds: int,
    scores: dict | list,
    outcome: str = "oylab_koradi",
    converted: int = 0,
    lead_won: int = 0,
    lead_price: float = 0.0,
    strengths: list[str] | None = None,
    weaknesses: list[str] | None = None,
    objections: list[str] | None = None,
    next_steps: str = "",
    longest_pause_seconds: float = 1.2,
    analyzed_at: str = "2026-11-27T14:00:00+05:00",
    created_at: str = "2026-11-27 14:00:00",
) -> dict:
    return {
        "call_id": call_id,
        "lead_id": lead_id,
        "manager_id": manager_id,
        "manager_name": manager_name,
        "client_name": f"Mijoz-{lead_id}",
        "duration_seconds": duration_seconds,
        "overall_score": overall_score,
        "scores": json.dumps(scores, ensure_ascii=False),
        "outcome": outcome,
        "converted": converted,
        "lead_won": lead_won,
        "lead_price": lead_price,
        "strengths": json.dumps(strengths or [], ensure_ascii=False),
        "weaknesses": json.dumps(weaknesses or [], ensure_ascii=False),
        "objections": json.dumps(objections or [], ensure_ascii=False),
        "next_steps": next_steps,
        "longest_pause_seconds": longest_pause_seconds,
        "summary": f"{manager_name} suhbati xulosasi",
        "analyzed_at": analyzed_at,
        "created_at": created_at,
    }


def test_empty_checklist_never_fabricates_scores():
    from src.services.core.metasell.checklist import evaluate_manager_checklist

    result = evaluate_manager_checklist([], manager_name="Nozima")
    assert result["available"] is False
    assert result["evaluated_calls"] == 0
    assert result["criteria"] == []
    assert result["strengths"] == []
    assert result["weaknesses"] == []


def test_manager_checklist_computes_real_micro_criteria_percentages():
    from src.services.core.metasell.checklist import evaluate_manager_checklist

    rows = [
        _make_call_row(
            call_id=f"nozima-{idx}",
            lead_id=100 + idx,
            manager_id=9,
            manager_name="Nozima Xudayberganova",
            overall_score=63,
            duration_seconds=286,
            scores={
                "salomlashish": 72,
                "ehtiyojlar": 74,
                "qiymat": 55,
                "etirozlar": 35,
                "yakunlash": 25,
                "muloqot_sifati": 68,
            },
            outcome="oylab_koradi",
            converted=0,
            lead_won=0,
            strengths=["Mijozni boʻlmasdan tingladi", "Portfolio keyslarini keltirdi"],
            weaknesses=[
                "Narxni vilka usulida emas, bitta raqam qilib aytdi",
                "Suhbat yakunida keyingi qadam va muddat tasdiqlanmadi",
                "Norasmiy ibora ishlatildi, subordinatsiya buzildi",
            ],
            objections=["Hozircha shart emas"],
            next_steps="N/A",
            longest_pause_seconds=5.2,
        )
        for idx in range(4)
    ]

    profile = evaluate_manager_checklist(rows, manager_name="Nozima Xudayberganova")
    assert profile["available"] is True
    assert profile["evaluated_calls"] == 4
    assert len(profile["criteria"]) == 8

    by_key = {item["key"]: item for item in profile["criteria"]}
    assert by_key["situation_discovery"]["pct"] >= 65.0
    assert by_key["context_and_greeting"]["pct"] >= 65.0
    assert by_key["closing_confirmation"]["pct"] < 40.0
    assert by_key["price_fork_discipline"]["pct"] < 50.0
    assert by_key["tone_subordination"]["pct"] < 65.0

    strength_keys = {item["key"] for item in profile["strengths"]}
    weakness_keys = {item["key"] for item in profile["weaknesses"]}
    assert "situation_discovery" in strength_keys
    assert "closing_confirmation" in weakness_keys
    assert "price_fork_discipline" in weakness_keys


def test_leaderboard_separates_sellers_from_talkers_and_sorts_both_modes():
    from src.services.core.metasell.leaderboard import (
        build_manager_leaderboard,
        export_leaderboard_csv,
    )

    rows = [
        _make_call_row(
            call_id="m-1",
            lead_id=201,
            manager_id=1,
            manager_name="Mohira Safarova",
            overall_score=60,
            duration_seconds=299,
            scores={"salomlashish": 65, "yakunlash": 80},
            outcome="tolov_kelishildi",
            converted=1,
            lead_won=1,
            lead_price=15_000_000,
            analyzed_at="2026-11-28T07:30:00+05:00",
        ),
        _make_call_row(
            call_id="m-2",
            lead_id=202,
            manager_id=1,
            manager_name="Mohira Safarova",
            overall_score=60,
            duration_seconds=299,
            scores={"salomlashish": 65, "yakunlash": 80},
            outcome="tolov_kelishildi",
            converted=1,
            lead_won=1,
            lead_price=20_000_000,
            analyzed_at="2026-11-28T07:45:00+05:00",
        ),
        _make_call_row(
            call_id="s-1",
            lead_id=301,
            manager_id=2,
            manager_name="Shahzoda Joʻrayeva",
            overall_score=65,
            duration_seconds=306,
            scores={"salomlashish": 75, "yakunlash": 20},
            outcome="oylab_koradi",
            converted=0,
            lead_won=0,
            analyzed_at="2026-11-28T07:20:00+05:00",
        ),
        _make_call_row(
            call_id="s-2",
            lead_id=302,
            manager_id=2,
            manager_name="Shahzoda Joʻrayeva",
            overall_score=65,
            duration_seconds=306,
            scores={"salomlashish": 75, "yakunlash": 20},
            outcome="oylab_koradi",
            converted=0,
            lead_won=0,
            analyzed_at="2026-11-28T07:25:00+05:00",
        ),
    ]

    by_result = build_manager_leaderboard(rows, sort_by="natija")
    assert by_result["has_data"] is True
    assert by_result["refresh_interval_minutes"] == 60
    assert by_result["last_analyzed_at"] == "2026-11-28T07:45:00+05:00"
    assert [m["manager_name"] for m in by_result["managers"]] == [
        "Mohira Safarova",
        "Shahzoda Joʻrayeva",
    ]

    mohira = by_result["managers"][0]
    shahzoda = by_result["managers"][1]
    assert mohira["sales_count"] == 2
    assert mohira["lead_conversion_pct"] == 100.0
    assert mohira["avg_duration_label"] == "4:59"
    assert mohira["diagnostic_tag"] == "sotyapti"

    assert shahzoda["sales_count"] == 0
    assert shahzoda["lead_conversion_pct"] == 0.0
    assert shahzoda["call_quality_pct"] == 65.0
    assert shahzoda["avg_duration_label"] == "5:06"
    assert shahzoda["diagnostic_tag"] == "faqat_gaplashyapti"

    by_quality = build_manager_leaderboard(rows, sort_by="sifat")
    assert [m["manager_name"] for m in by_quality["managers"]] == [
        "Shahzoda Joʻrayeva",
        "Mohira Safarova",
    ]

    # Formula injection guard in CSV export
    malicious = build_manager_leaderboard(
        [
            _make_call_row(
                call_id="x-1",
                lead_id=999,
                manager_id=99,
                manager_name="=CMD|' /C calc'!A0",
                overall_score=50,
                duration_seconds=120,
                scores={"salomlashish": 50},
            )
        ]
    )
    csv_text = export_leaderboard_csv(malicious["managers"])
    parsed = list(csv.reader(io.StringIO(csv_text)))
    assert parsed[0][:5] == [
        "Menejer",
        "Sotuvlar",
        "Lid konversiyasi (%)",
        "Suhbat sifati (%)",
        "Oʻrtacha davomiylik",
    ]
    assert parsed[1][0].startswith("'=CMD")


class _StubCursor:
    def __init__(self, rows: list[dict]):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _StubConn:
    def __init__(self, rows: list[dict]):
        self._rows = rows

    def execute(self, _sql: str, _params=()):
        return _StubCursor(self._rows)


class _StubDB:
    def __init__(self, rows: list[dict]):
        self._conn = _StubConn(rows)

    async def get_connection(self):
        return self._conn


@pytest.mark.asyncio
async def test_sales_chat_empty_db_never_hallucinates():
    from src.services.core.metasell.sales_chat import MetasellSalesChatEngine

    engine = MetasellSalesChatEngine(db=_StubDB([]), ai_router=None)
    reply = await engine.ask("Oʻtgan oyni eng yaxshi sotuvchisi kim?")

    assert reply["real_data"] is False
    assert reply["actions_count"] >= 1
    assert "topilmadi" in reply["answer"].lower()
    assert "Aziz" not in reply["answer"]
    assert "27,000,000" not in reply["answer"]


@pytest.mark.asyncio
async def test_sales_chat_executes_tools_and_resolves_followup_manager():
    from src.services.core.metasell.sales_chat import MetasellSalesChatEngine

    rows = [
        _make_call_row(
            call_id="m-1",
            lead_id=501,
            manager_id=11,
            manager_name="Mohira Safarova",
            overall_score=78,
            duration_seconds=299,
            scores={
                "salomlashish": 82,
                "ehtiyojlar": 80,
                "qiymat": 76,
                "etirozlar": 70,
                "yakunlash": 85,
                "muloqot_sifati": 78,
            },
            outcome="tolov_kelishildi",
            converted=1,
            lead_won=1,
            lead_price=25_000_000,
            strengths=["Mijozni boʻlmasdan tingladi", "Portfolio keyslarini keltirdi"],
            next_steps="Shartnoma yuborish",
        ),
        _make_call_row(
            call_id="n-1",
            lead_id=601,
            manager_id=12,
            manager_name="Nozima Xudayberganova",
            overall_score=63,
            duration_seconds=286,
            scores={
                "salomlashish": 70,
                "ehtiyojlar": 74,
                "qiymat": 50,
                "etirozlar": 35,
                "yakunlash": 25,
                "muloqot_sifati": 72,
            },
            outcome="oylab_koradi",
            converted=0,
            lead_won=0,
            strengths=["Faol tinglash"],
            weaknesses=[
                "Narxni bitta raqam qilib aytdi, vilka ishlatilmadi",
                "Suhbat yakunida keyingi qadam tasdiqlanmadi",
            ],
            objections=["Hozircha shart emas"],
            next_steps="N/A",
        ),
    ]

    engine = MetasellSalesChatEngine(db=_StubDB(rows), ai_router=None)

    first = await engine.ask("Eng yaxshi sotuvchi kim?")
    assert first["real_data"] is True
    assert first["actions_count"] >= 2
    assert first["focus_manager"] == "Mohira Safarova"
    assert "Mohira Safarova" in first["answer"]

    second = await engine.ask(
        "Nozima Xudayberganovaning kuchli va kuchsiz tomonlari qanday?",
        history=[{"role": "user", "content": "Eng yaxshi sotuvchi kim?"}, {"role": "assistant", "content": first["answer"], "focus_manager": first["focus_manager"]}],
    )
    assert second["focus_manager"] == "Nozima Xudayberganova"
    assert second["actions_count"] >= 2
    assert len(second["checklist"]["strengths"]) >= 1
    assert len(second["checklist"]["weaknesses"]) >= 1
    assert "Kuchli tomonlari" in second["answer"]
    assert "Kuchsiz tomonlari" in second["answer"]

    # Follow-up pronoun ("uning") resolves to Nozima Xudayberganova
    third = await engine.ask(
        "Uning asosiy eʼtirozlari nima?",
        history=[{"role": "assistant", "content": second["answer"], "focus_manager": second["focus_manager"]}],
    )
    assert third["focus_manager"] == "Nozima Xudayberganova"
    assert "Hozircha shart emas" in third["answer"]


@pytest.mark.asyncio
async def test_sales_chat_enforces_seller_rbac_isolation():
    from src.api.rbac import Principal, Role
    from src.services.core.metasell.sales_chat import MetasellSalesChatEngine

    rows = [
        _make_call_row(
            call_id="m-1",
            lead_id=501,
            manager_id=11,
            manager_name="Mohira Safarova",
            overall_score=80,
            duration_seconds=240,
            scores={"salomlashish": 80, "yakunlash": 85},
            outcome="tolov_kelishildi",
            converted=1,
            lead_won=1,
        ),
        _make_call_row(
            call_id="n-1",
            lead_id=601,
            manager_id=12,
            manager_name="Nozima Xudayberganova",
            overall_score=60,
            duration_seconds=200,
            scores={"salomlashish": 60, "yakunlash": 30},
        ),
    ]
    seller_principal = Principal(subject="12", role=Role.SELLER, auth_type="session")
    engine = MetasellSalesChatEngine(db=_StubDB(rows), ai_router=None)
    reply = await engine.ask("Eng yaxshi sotuvchi kim?", principal=seller_principal)

    assert "Mohira Safarova" not in reply["answer"]
    assert reply["focus_manager"] == "Nozima Xudayberganova"


def test_sales_quality_console_http_endpoints_and_cockpit_chat(monkeypatch):
    import base64
    from pathlib import Path
    from starlette.testclient import TestClient
    from src.api.routes.state import api_state
    from src.api_server import app
    from src.services.utils.free_ai_router import ProviderResult

    secret = "s" * 40
    monkeypatch.setenv("OISHA_API_SECRET", secret)
    headers = {"Authorization": f"Bearer {secret}"}

    rows = [
        _make_call_row(
            call_id="api-1",
            lead_id=801,
            manager_id=21,
            manager_name="Mohira Safarova",
            overall_score=76,
            duration_seconds=299,
            scores={"salomlashish": 80, "ehtiyojlar": 78, "yakunlash": 85},
            outcome="tolov_kelishildi",
            converted=1,
            lead_won=1,
            lead_price=18_000_000,
        ),
        _make_call_row(
            call_id="api-2",
            lead_id=802,
            manager_id=22,
            manager_name="Shahzoda Joʻrayeva",
            overall_score=65,
            duration_seconds=306,
            scores={"salomlashish": 72, "yakunlash": 20},
            outcome="oylab_koradi",
            converted=0,
            lead_won=0,
            weaknesses=["Narxni bitta raqam qilib aytdi, vilka ishlatmadi"],
        ),
    ]
    monkeypatch.setattr(api_state, "db_instance", _StubDB(rows))

    class _DummyRouter:
        async def generate_text(self, *_args, **_kwargs):
            raise RuntimeError("offline_in_unit_test")

        async def transcribe_audio(self, _audio_bytes: bytes, _mime: str):
            return ProviderResult("Eng yaxshi sotuvchi kim?", "groq", "whisper-large-v3")

    monkeypatch.setattr(
        "src.services.sales_quality.console_routes.get_free_ai_router",
        lambda: _DummyRouter(),
    )
    monkeypatch.setattr(
        "src.services.utils.free_ai_router.get_free_ai_router",
        lambda: _DummyRouter(),
    )

    client = TestClient(app)

    # 1. Unauthenticated fails closed (401)
    assert client.get("/api/sales-quality/leaderboard").status_code == 401

    # 2. Leaderboard JSON (natija vs sifat)
    lb_res = client.get("/api/sales-quality/leaderboard?days=30&sort_by=natija", headers=headers)
    assert lb_res.status_code == 200
    lb = lb_res.json()
    assert lb["real_data"] is True
    assert lb["managers"][0]["manager_name"] == "Mohira Safarova"
    assert lb["managers"][1]["diagnostic_tag"] == "faqat_gaplashyapti"

    # 3. Leaderboard CSV with UTF-8 BOM
    csv_res = client.get("/api/sales-quality/leaderboard.csv?days=30&sort_by=sifat", headers=headers)
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers["content-type"]
    assert csv_res.text.startswith("\ufeffMenejer,Sotuvlar")
    assert "Shahzoda Joʻrayeva" in csv_res.text

    # 4. Checklist JSON
    chk_res = client.get(
        "/api/sales-quality/checklist?manager_name=Shahzoda",
        headers=headers,
    )
    assert chk_res.status_code == 200
    chk = chk_res.json()
    assert chk["available"] is True
    assert chk["manager_name"] == "Shahzoda Joʻrayeva"

    # 5. Tool-calling text chat
    chat_res = client.post(
        "/api/sales-quality/chat",
        headers=headers,
        json={"question": "Eng yaxshi sotuvchi kim?", "days": 30},
    )
    assert chat_res.status_code == 200
    chat_body = chat_res.json()
    assert chat_body["actions_count"] == 3
    assert chat_body["focus_manager"] == "Mohira Safarova"

    # 6. Voice STT chat
    voice_b64 = base64.b64encode(b"RIFF....WAVEfmt ").decode("ascii")
    voice_res = client.post(
        "/api/sales-quality/chat/voice",
        headers=headers,
        json={"audio_base64": voice_b64, "mime_type": "audio/wav"},
    )
    assert voice_res.status_code == 200
    voice_body = voice_res.json()
    assert voice_body["transcript"] == "Eng yaxshi sotuvchi kim?"
    assert voice_body["focus_manager"] == "Mohira Safarova"

    # 7. Cockpit /api/dashboard/sales-chat/ask + zero fake demo text in HTML
    cockpit_res = client.post(
        "/api/dashboard/sales-chat/ask",
        headers=headers,
        json={"question": "Kim faqat gaplashyapti?"},
    )
    assert cockpit_res.status_code == 200
    assert cockpit_res.json()["focus_manager"] == "Shahzoda Joʻrayeva"

    cockpit_html = Path("src/api/templates/metasell_dashboard.html").read_text(encoding="utf-8")
    assert "27,000,000" not in cockpit_html
    assert "Aziz Karimov yetakchi" not in cockpit_html

    # 8. DB disconnected fails closed with 503
    monkeypatch.setattr(api_state, "db_instance", None)
    assert client.get("/api/sales-quality/leaderboard", headers=headers).status_code == 503
    assert client.post("/api/sales-quality/chat", headers=headers, json={"question": "Kim?"}).status_code == 503

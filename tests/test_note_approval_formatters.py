import json
from pathlib import Path

import pytest

from src.services.core.crm.note_approval.formatters import format_approval_message

SNAPSHOT = Path(__file__).parent / "fixtures" / "snapshots" / "note_approval_messages.json"

FULL = {
    "category": "Sotuv", "client_mood": "Ijobiy", "summary": "Logo <kerak>",
    "next_steps": "KP yuborish", "client_talk_pct": 60, "agent_talk_pct": 40,
    "sifat_bahosi": 77, "lead_bahosi": 140, "suhbat_oilasi": "Sotuv",
    "suhbat_domeni": "Branding", "baholash_rejimi": "To'liq", "biznes_mosligi": "Ha",
    "servis_yonalishi": "Logo", "mijoz_lavozimi": "CEO", "mijoz_kompaniya": "A&B",
    "qaror_qabul_qiluvchi": "Ha", "joylashuv": "Toshkent",
    "mijoz_malumotlari": ["a", "b", "c", "d", "e", "f"],
    "rubrik_baholar": {"salomlashish": 90, "ehtiyojlar": "55", "qiymat": None,
                       "etirozlar": -5, "yakunlash": 100, "muloqot_sifati": 33},
}

CASES = {
    "full": dict(analysis=FULL, lead_name="Ali <Vali>", phone="+998901234567", call_duration=125),
    "empty": dict(analysis={}, lead_name="", phone=""),
}


@pytest.mark.parametrize("name", sorted(CASES))
def test_format_approval_message_matches_snapshot(name):
    expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert format_approval_message(**CASES[name]) == expected[name]

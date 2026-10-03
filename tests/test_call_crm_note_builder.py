import json
from datetime import datetime
from pathlib import Path

import pytest

from src.services.call_analytics.crm_notes import CallCrmNotesMixin

SNAPSHOT = Path(__file__).parent / "fixtures" / "snapshots" / "call_crm_notes.json"


class _Omni:
    def format_crm_note_block(self):
        return "OMNI BLOCK"


class _Builder(CallCrmNotesMixin):
    max_transcript_note_chars = 40


FULL = {
    "summary": "  Logo kerak  ", "category": "Sotuv", "client_mood": "Ijobiy",
    "next_steps": "KP", "client_talk_pct": 55, "agent_talk_pct": 45,
    "talk_ratio_verdict": "Muvozanatli", "sifat_bahosi": 81, "lead_bahosi": 64,
    "suhbat_oilasi": "Sotuv", "baholash_rejimi": "To'liq",
    "rubrik_baholar": {"salomlashish": 90, "ehtiyojlar": "40", "etirozlar": 120},
    "natija": "uchrashuv", "uzilish_vaqti": "02:10", "uzilish_sababi": " narx ",
    "pauzalar": [{"vaqt": "01:00", "davomiyligi": 4}, {"vaqt": "03:00", "davomiyligi": 9}],
    "kuchli_tomonlar": ["a", "b", "c", "d"], "zaif_tomonlar": ["z"],
    "konversiya_tavsiyalari": ["t1"], "kelishilgan_vaqt": datetime(2026, 10, 5, 14, 30),
    "omnichannel_context": _Omni(),
}

CASES = {
    "full": dict(analysis=FULL, transcript_snippet="x" * 100),
    "no_rubric": dict(analysis={"rubrik_amal_qiladi": False, "talk_ratio_attributed": False,
                                "client_talk_pct": 30, "tavsiyalar": ["ignored"]}),
    "unattributed_zero": dict(analysis={"talk_ratio_attributed": False}),
    "legacy_kwargs": dict(analysis={}, summary="eski", category="X", client_mood="Salbiy",
                          next_steps=" ", client_talk_pct=10, agent_talk_pct=90,
                          talk_ratio_verdict="Ko'p gapirdi"),
}


@pytest.mark.parametrize("name", sorted(CASES))
def test_build_amocrm_note_matches_snapshot(name):
    expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert _Builder()._build_amocrm_note(**CASES[name]) == expected[name]

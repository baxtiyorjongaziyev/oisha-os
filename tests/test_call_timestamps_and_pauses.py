"""Vaqt belgisi, uzilish lahzasi va keraksiz pauza testlari.

REGRESSIYA XAVFI: vaqt belgisi `[01:42]` ICHIDA ikki nuqta bor. Uni olib
tashlamasdan yorliq ajratilsa, `[01` yorliq deb o'qiladi va gapirish
nisbati 0% ga tushadi — sotuvchi asossiz jazolanadi. Quyidagi testlar shu
uzilish qaytmasligini ta'minlaydi.
"""

import pytest
from unittest.mock import MagicMock

from src.services.core.call_analyzer import CallAnalyzer, _parse_breakdown_time
from src.services.core.sales_playbook import MAX_ACCEPTABLE_PAUSE_SECONDS
from src.services.utils.transcript import (
    detect_pauses,
    format_timestamp,
    parse_utterances,
    speaker_split,
    strip_timestamps,
)

TIMED = """[00:03] Sotuvchi: Assalomu alaykum Jon Branding
[00:09] Mijoz: Ha eshitaman sizni yaxshi
[00:40] Sotuvchi: Brending paketi haqida gaplashsak
[00:45] Mijoz: Qimmatga o'xshaydi menimcha"""


# ── Vaqt belgisi ─────────────────────────────────────────────────────────


def test_speaker_split_survives_timestamps():
    """Eng muhim regressiya: vaqt belgisi nisbatni buzmasligi kerak."""
    client_pct, agent_pct, attributed = speaker_split(TIMED)

    assert attributed is True
    assert client_pct > 0 and agent_pct > 0
    assert client_pct + agent_pct == 100


def test_speaker_split_matches_untimed_equivalent():
    """Vaqt belgisi qo'shilishi nisbatni O'ZGARTIRMASLIGI kerak."""
    assert speaker_split(TIMED) == speaker_split(strip_timestamps(TIMED))


def test_strip_timestamps_removes_only_the_marker():
    stripped = strip_timestamps("[00:03] Sotuvchi: Salom, soat 15:00 da")

    assert stripped == "Sotuvchi: Salom, soat 15:00 da"
    assert "15:00" in stripped  # matn ichidagi vaqt saqlanadi


@pytest.mark.parametrize("fmt", ["[00:03]", "[0:03]", "[01:00:03]"])
def test_timestamp_formats_accepted(fmt):
    assert parse_utterances(f"{fmt} A: salom")[0].speaker == "A"


def test_lines_without_timestamp_are_skipped():
    """Vaqtsiz qatordan pauza hisoblab bo'lmaydi — taxmin qilmaymiz."""
    assert parse_utterances("A: vaqtsiz qator") == []


def test_format_timestamp():
    assert format_timestamp(102) == "01:42"
    assert format_timestamp(0) == "00:00"
    assert format_timestamp(-5) == "00:00"


# ── Pauza ────────────────────────────────────────────────────────────────


def test_long_silence_detected():
    pauses = detect_pauses(TIMED, MAX_ACCEPTABLE_PAUSE_SECONDS)

    assert pauses, "31 soniyalik sukut topilishi kerak edi"
    assert max(p.gap_seconds for p in pauses) > 20


def test_natural_gaps_are_not_flagged():
    """Tabiiy, qisqa tanaffus xato deb ko'rsatilmasligi kerak."""
    natural = """[00:00] A: Salom men Aziz
[00:03] B: Ha salom
[00:05] A: Yaxshimisiz"""

    assert detect_pauses(natural, MAX_ACCEPTABLE_PAUSE_SECONDS) == []


def test_pause_needs_two_utterances():
    assert detect_pauses("[00:00] A: yolg'iz gap", 4.0) == []
    assert detect_pauses("", 4.0) == []


def test_pause_reports_who_went_silent():
    pause = detect_pauses(TIMED, MAX_ACCEPTABLE_PAUSE_SECONDS)[0]

    assert pause.after_speaker in {"Sotuvchi", "Mijoz"}
    assert ":" in pause.timestamp


# ── Uzilish lahzasi ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw,duration,expected",
    [
        ("01:42", 300, "01:42"),
        ("1:42", 300, "01:42"),
        ("00:00", 300, "00:00"),
        ("05:00", 120, None),   # davomiylikdan tashqarida — LLM to'qigan
        ("salom", 300, None),
        ("", 300, None),
        (None, 300, None),
        ("null", 300, None),
    ],
)
def test_breakdown_time_validation(raw, duration, expected):
    assert _parse_breakdown_time(raw, duration) == expected


def _analyzer():
    return CallAnalyzer(amocrm=MagicMock(), voice_processor=MagicMock(), db=MagicMock())


def test_breakdown_survives_into_analysis():
    result = _analyzer()._normalise_analysis(
        {
            "category": "Mijoz",
            "uzilish_vaqti": "00:45",
            "uzilish_sababi": "E'tirozga javob berilmadi",
        },
        TIMED + "\n[00:50] Sotuvchi: " + "so'z " * 40,
        60,
    )

    assert result["uzilish_vaqti"] == "00:45"
    assert result["uzilish_sababi"] == "E'tirozga javob berilmadi"


def test_reason_dropped_without_a_valid_time():
    """Vaqtsiz sabab rahbarga foydasiz — ikkalasi birga yashaydi."""
    result = _analyzer()._normalise_analysis(
        {"category": "Mijoz", "uzilish_vaqti": "aniqlanmadi",
         "uzilish_sababi": "Nimadir noto'g'ri"},
        TIMED,
        60,
    )

    assert result["uzilish_vaqti"] is None
    assert result["uzilish_sababi"] == ""


def test_breakdown_cleared_for_non_sales_calls():
    """'Mijoz yo'qolgan lahza' — savdo tushunchasi. Oila suhbatida mazmunsiz."""
    result = _analyzer()._normalise_analysis(
        {"category": "Oila", "uzilish_vaqti": "00:45", "uzilish_sababi": "x"},
        TIMED,
        60,
    )

    assert result["uzilish_vaqti"] is None


def test_pauses_measured_even_when_llm_fails():
    """Pauza LLM'ga bog'liq emas — fallback'da ham o'lchanadi."""
    result = _analyzer()._fallback_analysis(TIMED)

    assert result["pauzalar"], "fallback ham pauzani o'lchashi kerak"
    assert result["eng_uzun_pauza"] > 20


def test_timestamps_do_not_inflate_hallucination_guard():
    """Vaqt belgisi so'z sifatida sanalsa, haqiqiy matn rad etilardi."""
    from src.services.core.call_analyzer import _transcript_impossible_for_duration

    words = " ".join(f"[00:{i:02d}] A: so'z" for i in range(40))
    # 40 gap x 2 so'z = 80 so'z; 60s da 4 so'z/soniya chegarasi = 240 -> sig'adi
    assert _transcript_impossible_for_duration(words, 60) is False

"""Tests for source-backed payment promise extraction."""
from __future__ import annotations

from datetime import date, datetime, timezone

from src.services.evidence.payment_promises import (
    CLIENT,
    MANAGER,
    TASHKENT_TZ,
    SourceMessage,
    build_promise_report,
    extract_promises,
)

# Wednesday, 28 Oct 2026, 11:00 Tashkent
SAID_AT = datetime(2026, 10, 28, 11, 0, tzinfo=TASHKENT_TZ)


def _msg(text, role=CLIENT, said_at=SAID_AT, source="amocrm_note", sid="n1"):
    return SourceMessage(
        source=source,
        source_id=sid,
        speaker="Shaxboz aka" if role == CLIENT else "Rayxon",
        speaker_role=role,
        said_at=said_at,
        text=text,
        lead_id="L42",
    )


def test_tomorrow_with_amount_keeps_evidence():
    [p] = extract_promises(_msg("Assalomu alaykum. Ertaga 5 million to'layman."))
    assert p.promised_date == date(2026, 10, 29)
    assert p.date_ambiguous is False
    assert (p.amount, p.currency) == (5_000_000, "UZS")
    assert p.quote == "Ertaga 5 million to'layman."
    assert (p.source, p.source_id, p.lead_id) == ("amocrm_note", "n1", "L42")
    assert p.speaker == "Shaxboz aka"


def test_weekday_resolves_to_next_occurrence():
    [p] = extract_promises(_msg("Juma kuni pulni o'tkazaman"))
    assert p.promised_date == date(2026, 10, 30)


def test_explicit_month_date_and_year_rollover():
    [p] = extract_promises(_msg("15-noyabrgacha 500 ming so'm to'lab beraman"))
    assert p.promised_date == date(2026, 11, 15)
    assert (p.amount, p.currency) == (500_000, "UZS")

    [q] = extract_promises(_msg("10-yanvar to'layman"))
    assert q.promised_date == date(2027, 1, 10)


def test_vague_date_is_not_guessed():
    [p] = extract_promises(_msg("Oy oxirigacha to'layman, xavotir olmang"))
    assert p.promised_date is None
    assert p.date_ambiguous is True


def test_dollar_amounts():
    [a] = extract_promises(_msg("Ertaga $300 o'tkazaman"))
    assert (a.amount, a.currency) == (300, "USD")
    [b] = extract_promises(_msg("Ertaga 300 dollar to'layman"))
    assert (b.amount, b.currency) == (300, "USD")


def test_refusals_and_non_payment_text_are_not_promises():
    assert extract_promises(_msg("Hozir to'lay olmayman, pul yo'q")) == []
    assert extract_promises(_msg("Narx biroz qimmat ekan, o'ylab ko'raman")) == []
    assert extract_promises(_msg("15-noyabr kuni uchrashamiz")) == []


def test_curly_apostrophes_are_understood():
    [p] = extract_promises(_msg("Ertaga to‘layman"))
    assert p.promised_date == date(2026, 10, 29)


def test_date_uses_tashkent_day_not_utc():
    late_utc = datetime(2026, 10, 28, 20, 30, tzinfo=timezone.utc)  # 01:30 on 29th in Tashkent
    [p] = extract_promises(_msg("Ertaga to'layman", said_at=late_utc))
    assert p.promised_date == date(2026, 10, 30)


def test_naive_datetime_is_rejected():
    naive = datetime(2026, 10, 28, 11, 0)
    try:
        extract_promises(_msg("Ertaga to'layman", said_at=naive))
    except ValueError:
        return
    raise AssertionError("naive said_at must raise")


def test_report_separates_client_and_manager_and_flags_coverage():
    messages = [
        _msg("Ertaga 2 000 000 so'm to'layman", sid="n1"),
        _msg("Mijoz juma kuni to'laydi", role=MANAGER, sid="n2"),
        _msg("Oy oxirigacha to'layman", sid="c7", source="call_transcript"),
    ]
    report = build_promise_report(
        messages,
        source_status={"amocrm_note": "ok", "call_transcript": "ok", "telegram": "unavailable"},
    )
    assert [p.source_id for p in report.client_promises] == ["n1", "c7"]
    assert [p.source_id for p in report.manager_forecasts] == ["n2"]
    assert report.client_promises[0].amount == 2_000_000
    # Dated promises first, undated (ambiguous) last.
    assert report.promises[-1].promised_date is None
    assert report.unknown_sources == ["telegram"]
    assert report.complete is False


def test_report_complete_only_when_all_sources_ok():
    report = build_promise_report([], source_status={"amocrm_note": "ok"})
    assert report.complete is True
    assert build_promise_report([], source_status={}).complete is False


import pytest  # noqa: E402


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Bugun to'layman", date(2026, 10, 28)),
        ("Ertaga to'layman", date(2026, 10, 29)),
        ("Indinga to'layman", date(2026, 10, 30)),
        ("Payshanba kuni to'layman", date(2026, 10, 29)),  # next day
        ("Chorshanba kuni to'layman", date(2026, 11, 4)),  # same weekday -> next week
        ("Seshanba kuni to'layman", date(2026, 11, 3)),  # already passed this week
        ("15.11 kuni to'layman", date(2026, 11, 15)),
        ("15.11.2027 da to'layman", date(2027, 11, 15)),
        ("31-fevral to'layman", None),  # impossible date stays unresolved
    ],
)
def test_date_resolution_table(text, expected):
    [p] = extract_promises(_msg(text))
    assert p.promised_date == expected
    assert p.date_ambiguous is (expected is None)


@pytest.mark.parametrize(
    "text,amount,currency",
    [
        ("Ertaga 5 million to'layman", 5_000_000, "UZS"),
        ("Ertaga 5 mln so'm to'layman", 5_000_000, "UZS"),
        ("Ertaga 2,5 million to'layman", 2_500_000, "UZS"),
        ("Ertaga 750 ming so'm to'layman", 750_000, "UZS"),
        ("Ertaga 1 200 000 sum to'layman", 1_200_000, "UZS"),
        ("Ertaga 400 usd to'layman", 400, "USD"),
        ("Ertaga $ 1 500 o'tkazaman", 1_500, "USD"),
        ("Ertaga to'layman", None, None),
    ],
)
def test_amount_table(text, amount, currency):
    [p] = extract_promises(_msg(text))
    assert (p.amount, p.currency) == (amount, currency)


@pytest.mark.parametrize(
    "text",
    [
        "To'lamayman",
        "Ertaga to'lay olmayman",
        "Pul yo'q, bera olmayman",
        "Bu oy o'tkaza olmaymiz",
    ],
)
def test_negations_are_not_promises(text):
    assert extract_promises(_msg(text)) == []

from scripts.daily_sales_calls_report import RepStats, Report
from src.services.call_analytics.call_report_formatter import format_report_rop


def _report(reps):
    total = RepStats(account="Jami")
    for rep in reps:
        total.total += rep.total
        total.outgoing += rep.outgoing
        total.outgoing_answered += rep.outgoing_answered
        total.incoming += rep.incoming
        total.incoming_answered += rep.incoming_answered
        total.talk_seconds += rep.talk_seconds
        total.solid_calls += rep.solid_calls
    return Report(day="2026-10-29", reps=reps, total=total)


def test_same_display_name_accounts_are_merged():
    work = RepStats(
        account="rayxona@jonbranding.uz", total=3, outgoing=3,
        outgoing_answered=2, talk_seconds=120, solid_calls=1,
    )
    personal = RepStats(
        account="rayxona.personal@gmail.com", total=2, outgoing=2,
        outgoing_answered=1, talk_seconds=60,
    )
    names = {
        "rayxona@jonbranding.uz": "Rayxon",
        "rayxona.personal@gmail.com": "Rayxon",
    }

    text = format_report_rop(_report([work, personal]), names)

    assert text.count("1. Rayxon") == 1
    assert "Jami: <b>5</b>" in text
    assert "Javob: <b>3</b>" in text

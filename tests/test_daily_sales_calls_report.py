import importlib.util
import pathlib
import sys
from unittest.mock import MagicMock, patch

_PATH = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "daily_sales_calls_report.py"
_spec = importlib.util.spec_from_file_location("daily_sales_calls_report", _PATH)
rpt = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = rpt
_spec.loader.exec_module(rpt)


def _call(account, direction, answered, duration=0, t=1000, number="+998901112233", name=""):
    return {
        "user_account": account,
        "direction": direction,
        "answered": answered,
        "duration": duration,
        "start_time": t,
        "client_number": number,
        "client_name": name,
    }


def test_per_rep_stats():
    calls = [
        _call("a@x.uz", 1, 1, 120),
        _call("a@x.uz", 1, 0),
        _call("a@x.uz", 0, 1, 60),
        _call("b@x.uz", 1, 1, 30),
    ]
    rep = rpt.build_report(calls, "2026-09-29")
    a = next(r for r in rep.reps if r.account == "a@x.uz")
    assert (a.total, a.outgoing, a.incoming, a.answered, a.missed, a.talk_seconds) == (3, 2, 1, 2, 1, 180)
    assert a.avg_talk == 90
    assert rep.reps[0].account == "a@x.uz"  # ko'p gaplashgan birinchi
    assert rep.total.total == 4 and rep.total.talk_seconds == 210


def test_missed_incoming_without_callback():
    calls = [
        _call("a@x.uz", 0, 0, t=100, number="+998901111111"),
        _call("a@x.uz", 1, 1, 40, t=200, number="901111111"),  # qayta qo'ng'iroq qilingan
        _call("b@x.uz", 0, 0, t=300, number="+998902222222"),
        _call("b@x.uz", 0, 0, t=400, number="+998902222222"),  # dublikat
    ]
    rep = rpt.build_report(calls, "d")
    assert [c["client_number"] for c in rep.missed_no_callback] == ["+998902222222"]


def test_followup_next_day_clears_missed():
    calls = [_call("a@x.uz", 0, 0, t=100, number="+998903333333")]
    followup = [_call("a@x.uz", 1, 0, t=90000, number="+998903333333")]
    assert rpt.build_report(calls, "d", followup).missed_no_callback == []


def test_format_contains_rep_lines():
    rep = rpt.build_report([_call("farangiz@x.uz", 1, 1, 3725)], "2026-09-29")
    text = rpt.format_report(rep, {"farangiz@x.uz": "Farangiz"})
    assert "Farangiz" in text
    assert "1 soat 2 daq" in text
    assert "Ko'tarmadi" in text


def test_format_empty_day():
    assert "qo'ng'iroq bo'lmagan" in rpt.format_report(rpt.build_report([], "d"))


def test_fmt_duration():
    assert rpt.fmt_duration(45) == "45 son"
    assert rpt.fmt_duration(125) == "2 daq 5 son"
    assert rpt.fmt_duration(3 * 3600 + 600) == "3 soat 10 daq"


def test_parse_rep_names():
    assert rpt.parse_rep_names("A@x.uz:Ali, b@x.uz:Bek") == {"a@x.uz": "Ali", "b@x.uz": "Bek"}


def test_fetch_calls_paginates_and_uses_supervised():
    pages = [
        {"results": [{"id": 1}], "results_remains": 1, "results_next_offset": 100},
        {"results": [{"id": 2}], "results_remains": 0, "results_next_offset": 0},
    ]
    responses = [MagicMock(status_code=200, json=MagicMock(return_value=p)) for p in pages]
    with patch.object(rpt.requests, "post", side_effect=responses) as post:
        out = rpt.fetch_calls("admin@x.uz", "k", 1, 2, "test")
    assert out == [{"id": 1}, {"id": 2}]
    first = post.call_args_list[0]
    assert first.args[0] == "https://test.moizvonki.ru/api/v1"
    assert first.kwargs["json"]["supervised"] == 1
    assert post.call_args_list[1].kwargs["json"]["from_offset"] == 100


def test_exclude_admin_account():
    calls = [_call("admin@x.uz", 0, 0, number="+998904444444"), _call("a@x.uz", 1, 1, 10)]
    rep = rpt.build_report(calls, "d", exclude_accounts=["Admin@x.uz"])
    assert [r.account for r in rep.reps] == ["a@x.uz"]
    assert rep.missed_no_callback == []


def test_detailed_metrics():
    calls = [
        {**_call("a@x.uz", 0, 1, 50, t=36000, number="+998901"), "answer_time": 36012},
        {**_call("a@x.uz", 0, 1, 5, t=40000, number="+998902"), "answer_time": 40004},
        _call("a@x.uz", 1, 0, t=50000, number="+998901"),
    ]
    r = rpt.build_report(calls, "d").reps[0]
    assert (r.incoming_answered, r.incoming_missed, r.outgoing_missed) == (2, 0, 1)
    assert r.short_calls == 1
    assert r.avg_wait == 8
    assert len(r.clients) == 2
    assert r.answer_rate == 67
    assert (r.first_ts, r.last_ts) == (36000, 50000)


def test_admin_callback_counts_but_admin_not_listed():
    calls = [
        _call("a@x.uz", 0, 0, t=100, number="+998905555555"),
        _call("admin@x.uz", 1, 1, 30, t=200, number="+998905555555"),
    ]
    rep = rpt.build_report(calls, "d", exclude_accounts=["admin@x.uz"])
    assert rep.missed_no_callback == []
    assert [r.account for r in rep.reps] == ["a@x.uz"]


def test_split_message():
    text = "\n".join("x" * 100 for _ in range(100))
    chunks = rpt.split_message(text, limit=1000)
    assert all(len(c) <= 1000 for c in chunks)
    assert "\n".join(chunks) == text


def test_known_rep_without_calls_is_listed():
    calls = [_call("a@x.uz", 1, 1, 60)]
    rep = rpt.build_report(calls, "d", exclude_accounts=["admin@x.uz"],
                           known_accounts=["a@x.uz", "Farangiz@x.uz", "admin@x.uz"])
    assert [r.account for r in rep.reps] == ["a@x.uz", "Farangiz@x.uz"]
    text = rpt.format_report(rep, {"farangiz@x.uz": "Farangiz"})
    assert "Farangiz</b>\n   🚫 Qo'ng'iroq yo'q" in text
    assert "1 sotuvchi, 1 tasi qo'ng'iroqsiz" in text


def test_rop_feedback_over_50_calls():
    # 52 ta ko'targan va kamida 180 soniya (3 daqiqa) gaplashilgan suhbat
    calls = [_call("star@x.uz", 1, 1, 190) for _ in range(52)]
    rep = rpt.build_report(calls, "2026-10-06")
    text = rpt.format_report(rep, {"star@x.uz": "Star Rep"})
    assert "Star Rep</b> [50+ SIFATLI MARRA]" in text
    assert "Sifatli suhbat (≥3 daq): <b>52 ta</b>" in text
    assert "Barakalla!" in text
    assert "50 ta sifatli suhbat marrasini a'lo darajada bajardingiz!" in text


def test_rop_feedback_below_50_calls():
    # 10 ta javobli, lekin qisqa yoki yetarli bo'lmagan suhbat
    calls = [_call("junior@x.uz", 1, 1, 60) for _ in range(10)]
    rep = rpt.build_report(calls, "2026-10-06")
    text = rpt.format_report(rep, {"junior@x.uz": "Junior Rep"})
    assert "ROP Xulosasi va Ko'rsatmasi" in text
    assert "Sifatli suhbat (≥3 daq): <b>0 ta</b>" in text
    assert "Bu natija yetarli emas!" in text
    assert "kamida 50 ta ko'targan va 3+ daqiqa gaplashilgan" in text

import importlib.util
from datetime import datetime, timezone
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "tn_revenue_audit", Path(__file__).parent.parent / "scripts/prod/tn_revenue_audit.py"
)
audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(audit)


def test_phone_key_normalizes_formats():
    assert audit.phone_key("+998 90 670 00 20") == "906700020"
    assert audit.phone_key("998906700020") == "906700020"
    assert audit.phone_key("12") == ""


def test_name_tag():
    assert audit.name_tag("Ilhomjon aka (TN6)") == "TN6"
    assert audit.name_tag("Tadjimova Yulduz (T/N6)") == "TN6"
    assert audit.name_tag("Anvar aka") == ""


def test_build_rows_matches_by_phone_and_name_tag():
    groups = {"TN6": {"titles": ["TEZ NATIJA 6"], "start": datetime(2026, 7, 15, tzinfo=timezone.utc),
                      "end": None, "members": [
                          {"name": "Ali", "username": "ali", "phone": "998901112233"},
                          {"name": "Vali", "username": "", "phone": ""}]}}
    amo = {"901112233": [{"lead": "Logo", "price": 5_000_000, "closed": "2026-08-01"}]}
    at_clients = [{"name": "Ilhomjon aka (TN6)", "ltv": 8_400_000, "phone": "+998916617778"}]
    summary, detail = audit.build_rows(groups, amo, {}, at_clients)
    assert summary[0]["mijozga_aylangan"] == 2
    assert summary[0]["amocrm_summa"] == 5_000_000
    assert summary[0]["airtable_ltv"] == 8_400_000
    assert {d["manba"] for d in detail} == {"telefon", "ism belgisi"}

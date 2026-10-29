import json

from src.services.call_analytics.moizvonki_roster import (
    load_excludes,
    load_roster,
    parse_rep_names,
    unmapped_accounts,
)


def _write(tmp_path, reps, excludes=None):
    path = tmp_path / "roster.json"
    path.write_text(
        json.dumps({"reps": reps, "exclude_accounts": excludes or []}),
        encoding="utf-8",
    )
    return path


def test_parse_rep_names_normalizes_accounts():
    assert parse_rep_names("A@X.uz: Ali , b@x.uz:Vali") == {
        "a@x.uz": "Ali",
        "b@x.uz": "Vali",
    }


def test_file_is_source_of_truth_over_stale_env(tmp_path, monkeypatch):
    path = _write(tmp_path, {"mumtozmaxal@jonbranding.uz": "Mumtozmaxal"})
    monkeypatch.setenv(
        "MOIZVONKI_REP_NAMES", "farangiz@jonbranding.uz:Farangiz"
    )

    assert load_roster(path) == {"mumtozmaxal@jonbranding.uz": "Mumtozmaxal"}


def test_env_is_fallback_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("MOIZVONKI_REP_NAMES", "a@x.uz:Ali")
    missing = tmp_path / "missing.json"

    assert load_roster(missing) == {"a@x.uz": "Ali"}


def test_missing_file_and_env_returns_empty(tmp_path, monkeypatch):
    monkeypatch.delenv("MOIZVONKI_REP_NAMES", raising=False)

    assert load_roster(tmp_path / "missing.json") == {}


def test_load_excludes(tmp_path):
    path = _write(tmp_path, {"a@x.uz": "Ali"}, ["Owner@X.uz", " "])

    assert load_excludes(path) == {"owner@x.uz"}


def test_unmapped_accounts_skips_known_and_excluded():
    calls = [
        {"user_account": "mumtozmaxal@jonbranding.uz"},
        {"user_account": "new@jonbranding.uz"},
        {"user_account": "new@jonbranding.uz"},
        {"user_account": "admin@jonbranding.uz"},
        {"user_account": ""},
    ]

    result = unmapped_accounts(
        calls,
        {"mumtozmaxal@jonbranding.uz": "Mumtozmaxal"},
        ["admin@jonbranding.uz"],
    )

    assert result == {"new@jonbranding.uz": 2}

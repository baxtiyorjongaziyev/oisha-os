from datetime import datetime

import pytest

from scripts.amocrm_normalize_deal_phones import (
    AmoCRMDealPhoneNormalizer,
    CONFIRM_TEXT,
    normalize_uz_phone,
)


def _normalizer(live=False):
    normalizer = AmoCRMDealPhoneNormalizer.__new__(AmoCRMDealPhoneNormalizer)
    normalizer.live = live
    normalizer.confirm = CONFIRM_TEXT if live else ""
    normalizer.include_closed = False
    normalizer.limit = None
    normalizer.actions = []
    normalizer.errors = []
    normalizer.now = datetime(2026, 6, 4, 16, 0, 0)
    return normalizer


@pytest.mark.parametrize(
    ("raw", "normalized", "status", "reason"),
    [
        ("901234567", "+998901234567", "update", "local_9_digits"),
        ("998901234567", "+998901234567", "update", "missing_plus"),
        ("0901234567", "+998901234567", "update", "local_with_0_prefix"),
        ("+998 90 123 45 67", "+998901234567", "update", "format_plus_998"),
        ("+998901234567", "+998901234567", "ok", "already_plus_998"),
        ("+77011234567", None, "skip", "foreign_or_non_uz_international"),
        ("12345", None, "skip", "ambiguous_digits_len_5"),
    ],
)
def test_normalize_uz_phone(raw, normalized, status, reason):
    result = normalize_uz_phone(raw)

    assert result.normalized == normalized
    assert result.status == status
    assert result.reason == reason


def test_build_phone_values_preserves_enum_and_deduplicates():
    normalizer = _normalizer()

    values, results = normalizer.build_phone_values(
        [
            {"value": "901234567", "enum_code": "MOB"},
            {"value": "+998901234567", "enum_code": "WORK"},
        ]
    )

    assert values == [{"value": "+998901234567", "enum_code": "MOB"}]
    assert [result.status for result in results] == ["update", "skip"]
    assert results[1].reason == "duplicate_after_normalization"


def test_live_requires_confirm_before_network_calls():
    normalizer = _normalizer(live=True)
    normalizer.confirm = "wrong"

    with pytest.raises(SystemExit):
        normalizer.run()


def test_dry_run_records_contact_update_without_patch():
    normalizer = _normalizer(live=False)
    normalizer.request = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("no request in dry-run"))

    normalizer.patch_contact_phone(
        contact={"id": 12, "name": "Client"},
        lead_ids={101, 102},
        new_values=[{"value": "+998901234567", "enum_code": "MOB"}],
        results=[normalize_uz_phone("901234567")],
    )

    assert normalizer.actions[0]["action"] == "contact_phone_would_update"
    assert normalizer.actions[0]["contact_id"] == 12
    assert normalizer.actions[0]["lead_ids"] == [101, 102]

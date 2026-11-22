"""Seller attribution must never guess from a shared amoCRM login."""
import asyncio

from src.services.core.daily_priority.gatherer import gather_tasks
from src.services.core.daily_priority.ownership import resolve_seller_key

SALES = [
    {"key": "shahnoza", "name": "Shahnoza", "role": "sales"},
    {"key": "rayxona", "name": "Rayxona", "role": "sales"},
    {"key": "mumtozmaxal", "name": "Mumtozmaxal", "role": "sales"},
]


def lead_with_owner(value=None, tags=None):
    data = {
        "id": 31,
        "name": "Test lead",
        "status_id": 88871066,
        "price": 12_000_000,
        "responsible_user_id": 999,  # Shared account, not a seller identity.
        "_embedded": {"tags": [{"name": tag} for tag in (tags or [])]},
    }
    if value is not None:
        data["custom_fields_values"] = [{
            "field_name": "Sotuvchi",
            "values": [{"value": value}],
        }]
    return data


def test_seller_field_is_exact():
    assert resolve_seller_key(lead_with_owner("Rayxona"), SALES) == "rayxona"
    assert resolve_seller_key(lead_with_owner("Rayxon"), SALES) == "rayxona"
    assert resolve_seller_key(lead_with_owner("Rayxona VIP"), SALES) is None


def test_verified_tag_fallback_only():
    assert resolve_seller_key(lead_with_owner(tags=["Sotuvchi: Shahnoza"]), SALES) == "shahnoza"
    assert resolve_seller_key(lead_with_owner(tags=["Mumtozmaxal"]), SALES) == "mumtozmaxal"
    assert resolve_seller_key(lead_with_owner(tags=["Mumtozmaxal VIP"]), SALES) is None


def test_conflicting_evidence_is_blocked():
    assert resolve_seller_key(lead_with_owner("Rayxona", ["Shahnoza"]), SALES) is None
    assert resolve_seller_key(lead_with_owner("Unknown", ["Rayxona"]), SALES) is None
    assert resolve_seller_key(lead_with_owner(tags=["Rayxona", "Shahnoza"]), SALES) is None


def test_no_verified_owner_must_not_guess():
    assert resolve_seller_key(lead_with_owner(), SALES) is None
    assert resolve_seller_key({"responsible_user_id": 999}, SALES) is None


def test_daily_priority_never_round_robins_unknown_owner():
    async def fetch(_pipeline, status):
        if status == 88871066:
            return [
                lead_with_owner("Rayxona"),
                {"id": 32, "name": "Unassigned", "status_id": status, "price": 99_000_000},
            ]
        return []

    result = asyncio.run(gather_tasks(SALES, fetch=fetch, now_ts=1_700_000_000))
    assert [t["lead_id"] for t in result["rayxona"]] == [31]
    assert result["shahnoza"] == []
    assert result["mumtozmaxal"] == []


def test_menejer_custom_field_from_crm_setup_plan():
    lead = lead_with_owner()
    lead["custom_fields_values"] = [{
        "field_name": "Menejer",
        "field_id": 560001,
        "values": [{"value": "Rayxon"}],
    }]
    assert resolve_seller_key(lead, SALES) == "rayxona"


def test_field_id_metadata_verified_via_environment(monkeypatch):
    lead = lead_with_owner()
    # amoCRM may return an ID without field_name; never accept an unverified ID.
    lead["custom_fields_values"] = [{
        "field_id": 560001,
        "values": [{"value": "Shahnoza"}],
    }]
    monkeypatch.delenv("DAILY_PRIORITY_SELLER_FIELD_IDS", raising=False)
    assert resolve_seller_key(lead, SALES) is None
    monkeypatch.setenv("DAILY_PRIORITY_SELLER_FIELD_IDS", "560001")
    assert resolve_seller_key(lead, SALES) == "shahnoza"


def test_full_name_tags_generated_by_lead_assigner():
    assert resolve_seller_key(
        lead_with_owner(tags=["sotuvchi:Rayxona Rahimova"]), SALES
    ) == "rayxona"
    assert resolve_seller_key(
        lead_with_owner(tags=["sotuvchi:Shahnoza Abdijabborova"]), SALES
    ) == "shahnoza"
    assert resolve_seller_key(
        lead_with_owner(tags=["sotuvchi:Mumtozmaxal Normurodova"]), SALES
    ) == "mumtozmaxal"


def test_old_and_new_reassignment_tags_require_manual_reconciliation():
    lead = lead_with_owner(tags=[
        "sotuvchi:Rayxona Rahimova", "sotuvchi:Shahnoza Abdijabborova",
    ])
    assert resolve_seller_key(lead, SALES) is None


def test_menejer_and_tag_conflict_is_not_delivered():
    lead = lead_with_owner(tags=["sotuvchi:Shahnoza Abdijabborova"])
    lead["custom_fields_values"] = [{
        "field_name": "Menejer",
        "values": [{"value": "Rayxon"}],
    }]
    assert resolve_seller_key(lead, SALES) is None


def test_founder_deals_are_not_assigned_to_staff():
    lead = lead_with_owner()
    lead["custom_fields_values"] = [{
        "field_name": "Menejer",
        "values": [{"value": "Baxtiyorjon"}],
    }]
    assert resolve_seller_key(lead, SALES) is None


def test_daily_priority_full_name_seller_tag_is_not_lost():
    async def fetch(_pipeline, status):
        if status == 88871066:
            return [lead_with_owner(tags=["sotuvchi:Rayxona Rahimova"])]
        return []

    result = asyncio.run(gather_tasks(SALES, fetch=fetch, now_ts=1_700_000_000))
    assert [task["lead_id"] for task in result["rayxona"]] == [31]
    assert result["shahnoza"] == []
    assert result["mumtozmaxal"] == []

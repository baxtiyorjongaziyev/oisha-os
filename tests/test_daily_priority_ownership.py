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

"""Unit tests for the Canonical Team Roster (Single Source of Truth)."""
from __future__ import annotations

import sqlite3
import pytest

from src.services.core.crm.team_roster import (
    CANONICAL_STAFF,
    EXCLUDED_NON_STAFF_SLUGS,
    find_staff,
    format_hermes_roster_markdown,
    get_active_staff,
    get_known_manager_tags,
    get_moizvonki_rep_map,
    get_moizvonki_rep_names,
    get_rep_tg_usernames,
)
from src.services.core.crm.caller_id_service import resolve_rep
from src.services.core.hermes_crm_bridge import HermesCrmBridge


def test_canonical_staff_contains_all_verified_members():
    staff = get_active_staff(include_owner=True, db_path="nonexistent.db")
    slugs = {m.slug for m in staff}
    assert slugs == {
        "baxtiyorjon",
        "shahnoza",
        "rayxona",
        "mumtozmaxal",
        "hasanboy",
        "ifora",
        "ahroriy",
        "beslan",
        "dilbar",
    }
    # Excluded former staff and client names must never appear
    for ex in EXCLUDED_NON_STAFF_SLUGS:
        assert ex not in slugs


def test_find_staff_resolves_by_slug_alias_tg_id_username_and_email():
    # By slug & alias
    assert find_staff("rayxona").slug == "rayxona"
    assert find_staff("Rayxon").slug == "rayxona"
    assert find_staff("Mumtozmahal").slug == "mumtozmaxal"
    assert find_staff("Shahnoza Xayrullayevna").slug == "shahnoza"
    assert find_staff("БЕСЛАН").slug == "beslan"
    assert find_staff("Ahrorbek").slug == "ahroriy"

    # By Telegram user_id
    assert find_staff(8878762085).slug == "rayxona"
    assert find_staff("8802892610").slug == "shahnoza"

    # By Telegram @username
    assert find_staff("@RayxonJonbranding").slug == "rayxona"
    assert find_staff("@MumtozmaxalJonbranding").slug == "mumtozmaxal"

    # By Moizvonki email
    assert find_staff("mumtozmaxal@jonbranding.uz").slug == "mumtozmaxal"
    assert find_staff("xayrullayevna006@gmail.com").slug == "rayxona"

    # Excluded non-staff / clients must return None
    assert find_staff("Farangiz") is None
    assert find_staff("Oydin") is None
    assert find_staff("Dilnoza Muminova") is None
    assert find_staff("dilnoza") is None


def test_db_overrides_merge_cleanly(tmp_path):
    db_file = tmp_path / "dialer.db"
    conn = sqlite3.connect(db_file)
    conn.execute(
        """
        CREATE TABLE crm_seller_accounts (
            slug TEXT PRIMARY KEY,
            name TEXT,
            rep_id INTEGER,
            phone TEXT,
            tg TEXT,
            role TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO crm_seller_accounts VALUES ('mumtozmaxal', 'Mumtozmaxal Normurodova', 9000002, '+998773220098', '@MumtozNew', 'seller')"
    )
    # Excluded row in DB must be ignored
    conn.execute(
        "INSERT INTO crm_seller_accounts VALUES ('farangiz', 'Farangiz', 999, '+998900000000', '@farangiz', 'seller')"
    )
    conn.commit()
    conn.close()

    m = find_staff("mumtozmaxal", db_path=str(db_file))
    assert m is not None
    assert m.tg_username == "@MumtozNew"
    assert find_staff("farangiz", db_path=str(db_file)) is None


def test_caller_id_and_moizvonki_maps_use_ssot():
    rep_map = get_moizvonki_rep_map(db_path="nonexistent.db")
    assert "mumtozmaxal@jonbranding.uz" in rep_map
    assert "oydin@jonbranding.uz" not in rep_map
    assert "farangiz@jonbranding.uz" not in rep_map

    resolved = resolve_rep("mumtozmaxal@jonbranding.uz")
    assert resolved["slug"] == "mumtozmaxal"
    assert resolve_rep("oydin@jonbranding.uz")["slug"] == "unknown"


def test_rep_names_and_tg_usernames_and_manager_tags():
    names = get_moizvonki_rep_names(include_owner=False, db_path="nonexistent.db")
    assert names["shahnoza@jonbranding.uz"] == "Shahnoza Abdijabborova"
    assert names["rayxona@jonbranding.uz"] == "Rayxona"
    assert names["mumtozmaxal@jonbranding.uz"] == "Mumtozmaxal"

    tg_map = get_rep_tg_usernames(db_path="nonexistent.db")
    assert tg_map["rayxon"] == "@RayxonJonbranding"
    assert tg_map["mumtozmaxal"] == "@MumtozmaxalJonbranding"
    assert tg_map["shahnoza"] == "@jonbranding_assistant"

    tags = get_known_manager_tags(db_path="nonexistent.db")
    assert "mumtozmaxal" in tags
    assert "rayxon" in tags
    assert "farangiz" not in tags


def test_format_hermes_roster_markdown():
    md = format_hermes_roster_markdown(include_owner=False, db_path="nonexistent.db")
    assert "[Shahnoza Abdijabborova](tg://user?id=8802892610)" in md
    assert "[Mumtozmaxal Normurodova](tg://user?id=8940413540)" in md
    assert "Baxtiyorjon Gaziyev" not in md


@pytest.mark.asyncio
async def test_hermes_crm_bridge_get_team_roster():
    bridge = HermesCrmBridge(api=None)
    res = await bridge.get_team_roster(include_owner=False, role="seller")
    assert res["success"] is True
    assert res["source"] == "team_roster_ssot"
    slugs = [s["slug"] for s in res["staff"]]
    assert slugs == ["shahnoza", "rayxona", "mumtozmaxal"]
    assert "dilnoza" in res["excluded_non_staff"]

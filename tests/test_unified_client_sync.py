"""Unit tests for 5-system unified client profile sync."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from src.services.core.client_sync.adapters_contacts import (
    GoogleContactsUnifiedAdapter,
    SecondBrainUnifiedAdapter,
    TelegramContactsUnifiedAdapter,
    build_unified_notes,
)
from src.services.core.client_sync.adapters_crm import (
    AirtableUnifiedAdapter,
    AmoCRMUnifiedAdapter,
    profile_from_airtable_record,
    profile_from_amocrm_contact,
)
from src.services.core.client_sync.models import (
    UnifiedClientProfile,
    is_eligible_client,
    merge_profiles,
)
from src.services.core.client_sync.runner import run_unified_client_sync


@pytest.mark.parametrize(
    ("name", "phone", "expected"),
    [
        ("Hasan Gaziyev", "998973355900", True),
        ("Dilshod Karimov", "90-123-45-67", True),
        ("Автоконтакт +998901234567", "+998901234567", False),
        ("Autocontact 901234567", "901234567", False),
        ("Звонок на +998977005009", "+998977005009", False),
        ("Mijoz", "+998901234567", False),
        ("+998901234567", "+998901234567", False),
        ("Ali", "12345", False),
    ],
)
def test_is_eligible_client_filters_cold_and_invalid(name, phone, expected):
    parts = name.split(" ", 1)
    prof = UnifiedClientProfile(
        phone=phone,
        first_name=parts[0],
        last_name=parts[1] if len(parts) > 1 else "",
    )
    assert is_eligible_client(prof) is expected


def test_merge_profiles_combines_all_5_sources_without_data_loss():
    p_amo = profile_from_amocrm_contact(
        {
            "id": 101,
            "name": "Hasan Gaziyev",
            "custom_fields_values": [
                {"field_code": "PHONE", "values": [{"value": "998973355900"}]},
                {"field_code": "TELEGRAM_LOGIN", "values": [{"value": "@hasan_g"}]},
            ],
            "_embedded": {"tags": [{"name": "VIP"}]},
        },
        lead_id=505,
        stage="Shartnoma",
    )
    p_air = profile_from_airtable_record(
        {
            "id": "recABC123",
            "fields": {
                "Mijoz": "Hasan Gaziyev",
                "Telefon": "97-335-59-00",
                "Brend": "JonBranding",
                "Soha": "Brending",
                "Hudud": "Toshkent",
                "Teglar": ["Loyiha"],
            },
        }
    )
    assert p_amo is not None and p_air is not None
    assert p_amo.canonical_key == "+998973355900"
    assert p_air.canonical_key == "+998973355900"

    merged = merge_profiles([p_amo, p_air])
    assert merged.phone == "+998973355900"
    assert merged.full_name == "Hasan Gaziyev"
    assert merged.telegram_username == "hasan_g"
    assert merged.company == "JonBranding"
    assert merged.activity == "Brending"
    assert merged.region == "Toshkent"
    assert merged.amocrm_contact_id == 101
    assert merged.amocrm_lead_id == 505
    assert merged.airtable_record_id == "recABC123"
    assert merged.tags == ["Loyiha", "VIP"]
    notes = build_unified_notes(merged)
    assert "@hasan_g" in notes
    assert "JonBranding" in notes
    assert "recABC123" in notes


@pytest.mark.asyncio
async def test_run_unified_client_sync_writes_all_5_systems_and_skips_cold(tmp_path: Path):
    amo_calls, air_calls, g_calls, tg_calls = [], [], [], []

    fake_amo = SimpleNamespace(
        update_contact_phone=lambda name, phone: amo_calls.append(("update", name, phone)) or True,
        create_contact=lambda name, phone: amo_calls.append(("create", name, phone)) or 777,
    )
    fake_air = SimpleNamespace(
        create_record=lambda table, fields: air_calls.append((table, fields)) or {"id": "recNEW1"},
        update_record=lambda table, rid, fields: air_calls.append((table, rid, fields)) or True,
    )
    fake_google = SimpleNamespace(
        create_person=lambda first, last, phones, labels: g_calls.append((first, last, phones)) or "people/c1",
        update_person=lambda res, first, last, phones: g_calls.append((res, first, last, phones)) or True,
    )

    class _FakeTg:
        async def get_input_entity(self, ref):
            return f"entity:{ref}"

        async def __call__(self, req):
            tg_calls.append(req)
            return SimpleNamespace(users=[])

    raw_profiles = [
        UnifiedClientProfile(phone="998973355900", first_name="Hasan", last_name="Gaziyev", telegram_username="hasan_g", company="JonBranding"),
        UnifiedClientProfile(phone="+998901112233", first_name="Автоконтакт", last_name="+998901112233"),
    ]

    # 1. Dry-run writes nothing
    dry = await run_unified_client_sync(
        raw_profiles,
        sync_adapters=[
            AmoCRMUnifiedAdapter(fake_amo),
            AirtableUnifiedAdapter(fake_air),
            GoogleContactsUnifiedAdapter(fake_google),
            SecondBrainUnifiedAdapter([tmp_path]),
        ],
        async_adapters=[TelegramContactsUnifiedAdapter(_FakeTg(), daily_limit=10)],
        dry_run=True,
    )
    assert dry.eligible_clients == 1
    assert dry.skipped_ineligible == 1
    assert not amo_calls and not air_calls and not g_calls and not tg_calls
    assert not (tmp_path / "20-CLIENTS").exists()

    # 2. Apply mode writes all 5 systems cleanly (and NO _lead.md)
    live = await run_unified_client_sync(
        raw_profiles,
        sync_adapters=[
            AmoCRMUnifiedAdapter(fake_amo),
            AirtableUnifiedAdapter(fake_air),
            GoogleContactsUnifiedAdapter(fake_google),
            SecondBrainUnifiedAdapter([tmp_path]),
        ],
        async_adapters=[TelegramContactsUnifiedAdapter(_FakeTg(), daily_limit=10)],
        dry_run=False,
    )
    assert live.eligible_clients == 1
    assert live.errors == []
    assert live.per_system["amocrm"] == {"created": 1}
    assert live.per_system["airtable"] == {"created": 1}
    assert live.per_system["google_contacts"] == {"created": 1}
    assert live.per_system["second_brain"] == {"updated": 1}
    assert live.per_system["telegram_contacts"] == {"updated": 1}
    md_file = tmp_path / "20-CLIENTS" / "Hasan Gaziyev.md"
    assert md_file.is_file()
    content = md_file.read_text(encoding="utf-8")
    assert "+998973355900" in content
    assert "@hasan_g" in content
    assert "JonBranding" in content
    assert not list(tmp_path.rglob("_lead.md"))

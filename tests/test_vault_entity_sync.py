from pathlib import Path
from src.services.core.vault_entity_sync import (
    log_interaction_to_vault,
    sync_lead_to_vault,
    sync_person_to_vault,
)


def test_sync_person_and_lead_no_duplicate(tmp_path: Path):
    p1 = sync_person_to_vault(
        name="Ali Valiyev",
        phone="+998 90 123 45 67",
        telegram="@alivaliyev",
        vault_path=tmp_path,
    )
    assert p1 is not None and p1.exists()

    p2 = sync_person_to_vault(
        name="Ali (2)",
        phone="998901234567",
        tags=["TEZ-NATIJA-5"],
        vault_path=tmp_path,
    )
    assert p2 == p1

    lead = sync_lead_to_vault(
        lead_id=12345,
        lead_name="Ali Brending",
        phone="+998901234567",
        price=5000000,
        note="Birinchi qo'ng'iroq",
        vault_path=tmp_path,
    )
    assert lead is not None and lead.exists()
    assert "[[70-Odamlar/Ali Valiyev]]" in lead.read_text(encoding="utf-8")


def test_log_interaction_idempotent(tmp_path: Path):
    p = log_interaction_to_vault(
        person_name="Sardor",
        actor="Baxtiyorjon",
        channel="Telegram",
        summary="Narx bo'yicha kelishildi",
        phone="+998901112233",
        timestamp="2026-11-18 14:30",
        vault_path=tmp_path,
    )
    assert p is not None
    log_interaction_to_vault(
        person_name="Sardor",
        actor="Baxtiyorjon",
        channel="Telegram",
        summary="Narx bo'yicha kelishildi",
        phone="+998901112233",
        timestamp="2026-11-18 14:30",
        vault_path=tmp_path,
    )
    text = p.read_text(encoding="utf-8")
    assert text.count("Narx bo'yicha kelishildi") == 1
    assert "## Munosabatlar tarixi" in text

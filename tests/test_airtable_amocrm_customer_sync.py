"""Tests for Airtable -> AmoCRM Pokupateli (Customers) sync."""
from __future__ import annotations

from unittest.mock import MagicMock

from src.services.core.crm.airtable_customer_sync import (
    AirtableAmoCRMCustomerSync,
    _build_customer_note,
    _is_buying_customer,
)


def test_is_buying_customer():
    assert _is_buying_customer({"Loyihalari": ["rec1"], "Loyiha soni": 0, "LTV (real tushum)": 0})
    assert _is_buying_customer({"Loyihalari": [], "Loyiha soni": 1, "LTV (real tushum)": 0})
    assert _is_buying_customer({"Loyihalari": [], "Loyiha soni": 0, "LTV (real tushum)": 500000})
    assert not _is_buying_customer({"Loyihalari": [], "Loyiha soni": 0, "LTV (real tushum)": 0})


def test_build_customer_note_includes_projects():
    fields = {
        "Mijoz ismi": "Ali Valiyev",
        "Telefon raqami": "+998901234567",
        "Brands": "AliBrand",
        "Faoliyat turi": "Savdo",
        "Marketing kanali": "Instagram",
        "LTV (real tushum)": 10000000,
        "Jami qarzdorlik": 2000000,
        "Loyiha soni": 1,
    }
    projects = [
        {
            "id": "recProj1",
            "fields": {
                "Loyiha nomi": "Brending",
                "Xizmat turi": ["Logo", "Brendbuk"],
                "Loyiha bosqichi": "Jarayonda",
                "Jami loyiha narxi (UZS)": 12000000,
                "Jami to'langan (UZS)": 10000000,
                "Qoldiq to‘lov (UZS)": 2000000,
                "Start sana": "2026-10-01",
                "END sana": "2026-11-01",
            },
        }
    ]
    note = _build_customer_note(fields, projects)
    assert "Ali Valiyev" in note
    assert "AliBrand" in note
    assert "Brending" in note
    assert "Logo, Brendbuk" in note
    assert "10,000,000 UZS" in note


def test_sync_all_creates_and_updates_customers():
    mijozlar_airtable = MagicMock()
    mijozlar_airtable.get_projects.return_value = [
        {
            "id": "recCust1",
            "fields": {
                "Mijoz ismi": "Ali Valiyev",
                "Telefon raqami": "+998901234567",
                "Brands": "AliBrand",
                "Loyihalari": ["recProj1"],
                "Loyiha soni": 1,
                "LTV (real tushum)": 5000000,
                "Jami qarzdorlik": 1000000,
                "Xizmat turi": ["Logo"],
                "Marketing kanali": "Instagram",
            },
        },
        {
            "id": "recCust2",
            "fields": {
                "Mijoz ismi": "Sotib Olmagan",
                "Loyihalari": [],
                "Loyiha soni": 0,
                "LTV (real tushum)": 0,
            },
        },
    ]

    loyihalar_airtable = MagicMock()
    loyihalar_airtable.get_projects.return_value = [
        {
            "id": "recProj1",
            "fields": {
                "Loyiha nomi": "AliBrand Logo",
                "Xizmat turi": ["Logo"],
                "Loyiha bosqichi": "Yakunlandi",
                "Jami loyiha narxi (UZS)": 6000000,
                "Jami to'langan (UZS)": 5000000,
                "Qoldiq to‘lov (UZS)": 1000000,
            },
        }
    ]

    amocrm = MagicMock()
    amocrm.get_contact_by_phone.return_value = {"id": 101}
    amocrm.find_customer.return_value = None
    amocrm.create_customer.return_value = 501

    syncer = AirtableAmoCRMCustomerSync(
        amocrm=amocrm,
        mijozlar_airtable=mijozlar_airtable,
        loyihalar_airtable=loyihalar_airtable,
    )
    stats = syncer.sync_all(force_refresh=True)

    assert stats["total_airtable_customers"] == 2
    assert stats["buying_customers"] == 1
    assert stats["created"] == 1
    assert stats["skipped"] == 1
    assert stats["errors"] == 0
    amocrm.create_customer.assert_called_once()
    amocrm.add_customer_note.assert_called_once()
    amocrm.add_customer_transaction.assert_called_once_with(
        customer_id=501,
        price=5000000,
        comment="AliBrand Logo (Logo)",
    )

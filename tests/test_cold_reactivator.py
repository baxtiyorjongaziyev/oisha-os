import pytest
from unittest.mock import MagicMock, patch

from src.services.core.leads.cold_reactivator import (
    ColdLeadReactivator,
    extract_lead_notes_summary,
    synthesize_client_playbook,
)


def test_extract_lead_notes_summary():
    notes = [
        {"params": {"text": "Facebook Lead Ads orqali avtomatik tushdi.\nBrend / Biznes nomi: Test Brend"}},
        {"params": {"text": "[AI_CALL_ANALYSIS] Oisha AI: Men Jon Brandingdan Shahnozaman."}},
        {"params": {"text": "Oddiy eslatma matni"}},
    ]
    summary = extract_lead_notes_summary(notes)
    assert len(summary["forms"]) == 1
    assert len(summary["call_analyses"]) == 1
    assert len(summary["general"]) == 1
    assert summary["previous_manager"] == "Shahnoza"


def test_synthesize_client_playbook():
    summary = {
        "call_analyses": ["[AI_CALL_ANALYSIS] Mijoz logotip va nom bilan qiziqqan."],
        "forms": ["Brend nomi: Test Mebel"],
        "general": [],
        "previous_manager": "Rayxona",
    }
    playbook = synthesize_client_playbook("Test Lead", "Ali", "+998901234567", summary)
    assert "MIJOZ TARIXI" in playbook
    assert "MUNOSABAT O'RNATISH" in playbook
    assert "Ali" in playbook or "Test Lead" in playbook


@patch("src.services.core.leads.cold_reactivator.requests")
@patch("src.services.core.leads.cold_reactivator._load_seen_leads")
def test_fetch_candidate_cold_leads(mock_seen, mock_requests):
    mock_seen.return_value = {111}
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "_embedded": {
            "leads": [
                {"id": 111, "name": "Seen Lead", "_embedded": {"contacts": [{"id": 1}]}},
                {"id": 222, "name": "Fresh Lead", "_embedded": {"contacts": [{"id": 2}]}},
            ]
        }
    }
    mock_requests.get.return_value = mock_resp

    reactivator = ColdLeadReactivator(amo=MagicMock())
    reactivator.amo._get_headers.return_value = {}
    reactivator.amo.base_url = "https://test.amocrm.ru"

    candidates = reactivator.fetch_candidate_cold_leads(limit=5)
    assert len(candidates) == 1
    assert candidates[0]["id"] == 222


@patch("src.services.core.leads.cold_reactivator.requests")
@patch("src.services.core.leads.cold_reactivator._save_seen_leads")
@patch("src.services.core.leads.cold_reactivator._load_seen_leads")
def test_reactivate_lead(mock_load_seen, mock_save_seen, mock_requests):
    mock_load_seen.return_value = set()
    mock_resp_notes = MagicMock()
    mock_resp_notes.status_code = 200
    mock_resp_notes.json.return_value = {"_embedded": {"notes": []}}

    mock_resp_contact = MagicMock()
    mock_resp_contact.status_code = 200
    mock_resp_contact.json.return_value = {"id": 10, "name": "Mijoz", "custom_fields_values": []}

    mock_resp_create = MagicMock()
    mock_resp_create.status_code = 201
    mock_resp_create.json.return_value = {"_embedded": {"leads": [{"id": 999}]}}

    mock_requests.get.side_effect = [mock_resp_notes, mock_resp_notes, mock_resp_contact]
    mock_requests.post.return_value = mock_resp_create

    reactivator = ColdLeadReactivator(amo=MagicMock())
    reactivator.amo._get_headers.return_value = {}
    reactivator.amo.base_url = "https://test.amocrm.ru"

    orig = {"id": 555, "name": "Eski Bitim", "_embedded": {"contacts": [{"id": 10}]}}
    new_id = reactivator.reactivate_lead(orig)

    assert new_id == 999
    assert mock_requests.post.call_count >= 2  # 1 for lead, 1 for note

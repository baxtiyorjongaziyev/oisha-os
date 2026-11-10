"""Unit tests for safe CRM Drive orchestration (no external network)."""
import asyncio
from unittest.mock import Mock, AsyncMock
import pytest

from src.services.core.crm.safe_drive_automation import (
    SafeCRMDriveAutomation, CopyRecord,
)


def _service():
    amo = Mock()
    amo.base_url = "https://example.amocrm.ru"
    amo.get_lead_notes = AsyncMock(return_value=[])
    amo.add_lead_note.return_value = {"ok": True}
    drive = Mock()
    drive.service.files.return_value.list.return_value.execute.return_value = {"files": []}
    drive.create_folder.return_value = "folder-123"
    return SafeCRMDriveAutomation(amo, drive, "root-123"), amo, drive


def test_missing_root_is_rejected():
    with pytest.raises(ValueError):
        SafeCRMDriveAutomation(Mock(), Mock(), "")


def test_folder_created_and_crm_link_written():
    automation, amo, drive = _service()
    folder = asyncio.run(automation.ensure_lead_folder(42))
    assert folder == "folder-123"
    drive.create_folder.assert_called_once_with("amoCRM_Lead_42", "root-123")
    note = amo.add_lead_note.call_args.args[1]
    assert "https://drive.google.com/drive/folders/folder-123" in note
    assert "https://example.amocrm.ru/leads/detail/42" in note


def test_existing_folder_and_link_are_reused():
    automation, amo, drive = _service()
    drive.service.files.return_value.list.return_value.execute.return_value = {
        "files": [{"id": "folder-123"}]
    }
    amo.get_lead_notes.return_value = [
        {"params": {"text": "[OISHA_DRIVE_FOLDER] folder-123"}}
    ]
    assert asyncio.run(automation.ensure_lead_folder(42)) == "folder-123"
    drive.create_folder.assert_not_called()
    amo.add_lead_note.assert_not_called()


def test_deletion_requires_explicit_approval():
    automation, amo, _ = _service()
    record = CopyRecord(42, 7, "uuid", "drive-id", "https://example", "hash", 2)
    with pytest.raises(PermissionError):
        asyncio.run(automation.delete_approved_original(
            record, approval_id="not-approved", acting_owner_id=0
        ))
    amo.delete_note.assert_not_called()


def test_staging_ignores_non_file_notes():
    automation, amo, _ = _service()
    assert asyncio.run(automation.stage_file(42, {
        "id": 8, "note_type": "common",
    })) is None
    amo.download_file.assert_not_called()

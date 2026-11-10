"""Safe amoCRM -> Google Drive orchestration.

Never deletes CRM content automatically. The destructive operation requires a
separate approval call AND a verified persisted copy.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import tempfile
from dataclasses import dataclass
from typing import Any, Optional

from src.services.core.crm.amocrm_sync import AmoCRMSync
from src.services.core.gdrive import GoogleDriveSync

log = logging.getLogger(__name__)
LINK_MARKER = "[OISHA_DRIVE_FOLDER]"
COPY_MARKER = "[OISHA_DRIVE_COPY]"


@dataclass
class CopyRecord:
    lead_id: int
    note_id: int
    file_id: str
    drive_id: str
    drive_url: str
    sha256: str
    size: int


class SafeCRMDriveAutomation:
    """Sync CRM lead folders and stage verified copies for explicit approval."""

    def __init__(self, amo: AmoCRMSync, drive: GoogleDriveSync, root_folder_id: str):
        if not root_folder_id:
            raise ValueError("Set GDRIVE_OFFLOAD_FOLDER_ID before enabling automation")
        self.amo = amo
        self.drive = drive
        self.root = root_folder_id

    def _find_folder(self, lead_id: int) -> Optional[dict[str, Any]]:
        # A stable numeric ID ensures renamed leads reuse the same folder.
        name = f"amoCRM_Lead_{lead_id}"
        safe = name.replace("'", "\\'")
        response = self.drive.service.files().list(
            q=f"name = '{safe}' and '{self.root}' in parents and "
              "mimeType = 'application/vnd.google-apps.folder' and trashed = false",
            fields="nextPageToken,files(id,name,webViewLink)",
            pageSize=100, supportsAllDrives=True, includeItemsFromAllDrives=True,
        ).execute()
        return next(iter(response.get("files", [])), None)

    async def ensure_lead_folder(self, lead_id: int) -> str:
        """Creates/reuses a folder and writes a searchable CRM back-link."""
        existing = await asyncio.to_thread(self._find_folder, lead_id)
        folder_id = existing["id"] if existing else await asyncio.to_thread(
            self.drive.create_folder, f"amoCRM_Lead_{lead_id}", self.root
        )
        if not folder_id:
            raise RuntimeError(f"Google Drive folder creation failed for lead {lead_id}")
        url = f"https://drive.google.com/drive/folders/{folder_id}"
        notes = await self.amo.get_lead_notes(lead_id)
        if getattr(self.amo, "last_error", None):
            raise RuntimeError("CRM notes unavailable; refusing duplicate link")
        marker = f"{LINK_MARKER} {folder_id}"
        if not any(marker in n.get("params", {}).get("text", "") for n in notes):
            crm_url = f"{self.amo.base_url}/leads/detail/{lead_id}"
            saved = await asyncio.to_thread(
                self.amo.add_lead_note, lead_id,
                f"{marker}\nGoogle Drive: {url}\namoCRM: {crm_url}",
            )
            if not saved:
                raise RuntimeError(f"CRM link note write failed for lead {lead_id}")
        return folder_id

    async def stage_file(self, lead_id: int, note: dict[str, Any]) -> Optional[CopyRecord]:
        """Copy and verify bytes, then save a CRM receipt; never delete original."""
        if note.get("note_type") != "file":
            return None
        params = note.get("params") or {}
        file_uuid = params.get("file_uuid")
        note_id = int(note["id"])
        if not file_uuid:
            return None
        notes = await self.amo.get_lead_notes(lead_id)
        if getattr(self.amo, "last_error", None):
            raise RuntimeError("CRM notes unavailable; refusing duplicate copy")
        existing_tag = f"{COPY_MARKER} lead={lead_id} note={note_id}"
        if any(existing_tag in n.get("params", {}).get("text", "") for n in notes):
            return None
        data = await asyncio.to_thread(self.amo.download_file, file_uuid)
        if not data:
            raise RuntimeError(f"CRM download failed for note {note_id}")
        folder_id = await self.ensure_lead_folder(lead_id)
        file_name = os.path.basename(params.get("file_name") or f"file_{note_id}")
        digest = hashlib.sha256(data).hexdigest()
        # Stable name makes retries and duplicate detection possible.
        name = f"{note_id}_{file_name}"
        with tempfile.NamedTemporaryFile(delete=False) as handle:
            handle.write(data)
            path = handle.name
        try:
            from googleapiclient.http import MediaFileUpload
            media = MediaFileUpload(path, resumable=True, mimetype="application/octet-stream")
            def upload_and_verify():
                matches = self.drive.service.files().list(
                    q=f"'{folder_id}' in parents and trashed = false",
                    fields="nextPageToken,files(id,name,size,md5Checksum,webViewLink)",
                    pageSize=1000, supportsAllDrives=True, includeItemsFromAllDrives=True,
                ).execute().get("files", [])
                matches = [f for f in matches if f.get("name") == name]
                remote = matches[0] if matches else self.drive.service.files().create(
                    body={"name": name, "parents": [folder_id]},
                    media_body=media, fields="id,name,size,md5Checksum,webViewLink", supportsAllDrives=True
                ).execute()
                if int(remote.get("size", -1)) != len(data):
                    raise RuntimeError("Drive size verification failed")
                if remote.get("md5Checksum") != hashlib.md5(data).hexdigest():
                    raise RuntimeError("Drive checksum verification failed")
                return remote
            remote = await asyncio.to_thread(upload_and_verify)
        finally:
            os.remove(path)
        file_id = remote["id"]
        url = remote.get("webViewLink") or f"https://drive.google.com/file/d/{file_id}/view"
        receipt = (f"{existing_tag} drive={file_id} sha256={digest} size={len(data)}"
                   f"\nVerified Google Drive copy: {url}\nCRM original retained.")
        saved = await asyncio.to_thread(self.amo.add_lead_note, lead_id, receipt)
        if not saved:
            raise RuntimeError("Drive copy verified, but CRM receipt write failed; original retained")
        return CopyRecord(lead_id, note_id, file_uuid, file_id, url, digest, len(data))

    async def stage_lead(self, lead_id: int) -> dict[str, int]:
        await self.ensure_lead_folder(lead_id)
        notes = await self.amo.get_lead_notes(lead_id)
        if getattr(self.amo, "last_error", None):
            raise RuntimeError("CRM notes unavailable for file staging")
        result = {"copied": 0, "skipped": 0, "errors": 0}
        for n in notes:
            if n.get("note_type") != "file":
                continue
            try:
                copied = await self.stage_file(lead_id, n)
                result["copied" if copied else "skipped"] += 1
            except Exception:
                log.exception("CRM->Drive stage failed for lead=%s note=%s", lead_id, n.get("id"))
                result["errors"] += 1
        return result

    async def delete_approved_original(
        self, record: CopyRecord, *, approval_id: str, acting_owner_id: int,
    ) -> bool:
        """Delete ONLY after a one-time, owner-claimed approval in Turso DB.

        The Telegram callback verifies the sender; this method independently
        checks the durable claim so a guessed string cannot authorize deletion.
        """
        from src.settings import settings
        from src.database_pool import db_pool
        if not settings.OWNER_ID or int(acting_owner_id) != int(settings.OWNER_ID):
            raise PermissionError("Only the configured owner may approve deletion")
        rows = await db_pool.execute(
            "SELECT lead_id, note_id, drive_id, size, sha256 FROM "
            "crm_drive_delete_approvals WHERE id = ? AND status = 'processing' "
            "AND resolved_by = ?",
            [approval_id, int(acting_owner_id)],
        )
        if len(rows) != 1:
            raise PermissionError("Missing one-time, claimed approval")
        grant = rows[0]
        if (int(grant["lead_id"]) != record.lead_id or
                int(grant["note_id"]) != record.note_id or
                str(grant["drive_id"]) != record.drive_id or
                int(grant["size"]) != record.size or
                str(grant["sha256"]) != record.sha256):
            raise PermissionError("Approval does not match verified file")
        notes = await self.amo.get_lead_notes(record.lead_id)
        if getattr(self.amo, "last_error", None):
            raise RuntimeError("CRM notes unavailable; refusing deletion")
        receipt = f"{COPY_MARKER} lead={record.lead_id} note={record.note_id}"
        if not any(receipt in n.get("params", {}).get("text", "") and
                   f"drive={record.drive_id}" in n.get("params", {}).get("text", "")
                   for n in notes):
            raise PermissionError("Verified copy receipt is missing")
        remote = await asyncio.to_thread(
            lambda: self.drive.service.files().get(
                fileId=record.drive_id, fields="id,size,md5Checksum,trashed", supportsAllDrives=True
            ).execute()
        )
        if remote.get("trashed") or int(remote.get("size", -1)) != record.size:
            raise RuntimeError("Drive copy unavailable or size mismatch")
        # Re-download to verify real bytes before irreversible CRM action.
        from googleapiclient.http import MediaIoBaseDownload
        import io
        def verify_remote():
            buf = io.BytesIO()
            downloader = MediaIoBaseDownload(
                buf, self.drive.service.files().get_media(fileId=record.drive_id, supportsAllDrives=True)
            )
            done = False
            while not done:
                _, done = downloader.next_chunk()
            return hashlib.sha256(buf.getvalue()).hexdigest()
        if await asyncio.to_thread(verify_remote) != record.sha256:
            raise RuntimeError("Drive content hash mismatch")
        return bool(await self.amo.delete_note("leads", record.lead_id, record.note_id))

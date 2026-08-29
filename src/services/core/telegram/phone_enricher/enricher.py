"""
TelegramPhoneEnricher main class for searching usernames and patching contacts.
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
import structlog
import requests

from src.services.core.telegram.phone_enricher.models import (
    ENRICHMENT_TAG,
    NO_PHONE_TAG,
    PHONE_RE,
    TME_RE,
    USERNAME_RE,
    EnrichmentReport,
    EnrichmentResult,
    extract_existing_phones,
    extract_usernames,
    normalize_phone,
    report_to_dict,
)

logger = structlog.get_logger()

class TelegramPhoneEnricher:
    """Find AmoCRM contacts without phone numbers and try to resolve them via Telegram."""

    def __init__(
        self,
        amocrm: Any,
        tg_client: Any,
        rate_limit_sec: float = 1.5,
    ):
        self.amocrm = amocrm
        self.tg_client = tg_client
        self.rate_limit_sec = rate_limit_sec

    # -----------------------
    # Public API
    # -----------------------

    async def run(self, limit: int = 200, dry_run: bool = True) -> EnrichmentReport:
        """Main entrypoint. Scans contacts, attempts enrichment.

        Args:
            limit: maksimal contact soni
            dry_run: True bo'lsa AmoCRM ga hech narsa yozilmaydi
        """
        report = EnrichmentReport(
            generated_at=datetime.now(timezone.utc).isoformat(),
            dry_run=dry_run,
        )

        contacts = await self._fetch_contacts(limit=limit)
        report.checked = len(contacts)
        logger.info(f"[ENRICH] Tekshirilayotgan contactlar: {len(contacts)}")

        for contact in contacts:
            existing = extract_existing_phones(contact)
            if existing:
                continue  # phone already present
            report.no_phone += 1

            result = await self._enrich_contact(contact, dry_run=dry_run)
            report.results.append(result)

            if result.status == "found" or result.status == "dry_run":
                report.resolved += 1
            if result.status == "applied":
                report.applied += 1
            if result.status == "hidden":
                report.hidden += 1
            if result.status == "error":
                report.errors += 1

            await asyncio.sleep(self.rate_limit_sec)

        logger.info(
            f"[ENRICH] Yakun: tekshirildi={report.checked}, raqamsiz={report.no_phone}, "
            f"topildi={report.resolved}, qo'llanildi={report.applied}, "
            f"yashirin={report.hidden}, xato={report.errors}"
        )
        return report

    # -----------------------
    # Contact loading
    # -----------------------

    async def _fetch_contacts(self, limit: int) -> List[Dict[str, Any]]:
        """Fetches contacts from AmoCRM in pages until `limit` reached."""
        contacts: List[Dict[str, Any]] = []
        page = 1
        page_size = min(250, max(50, limit))
        while len(contacts) < limit:
            batch = await asyncio.to_thread(self._get_contacts_page, page, page_size)
            if not batch:
                break
            contacts.extend(batch)
            if len(batch) < page_size:
                break
            page += 1
        return contacts[:limit]

    def _get_contacts_page(self, page: int, page_size: int) -> List[Dict[str, Any]]:
        """Synchronously hit AmoCRM contacts endpoint."""
        self.amocrm._load_token()
        url = f"{self.amocrm.base_url}/api/v4/contacts"
        params = {
            "limit": page_size,
            "page": page,
            "order[updated_at]": "desc",
            "with": "leads",
        }
        try:
            resp = requests.get(
                url,
                headers=self.amocrm._get_headers(),
                params=params,
                timeout=30,
            )
            if resp.status_code == 200:
                return resp.json().get("_embedded", {}).get("contacts", []) or []
            if resp.status_code == 401 and self.amocrm.refresh_token():
                resp = requests.get(
                    url,
                    headers=self.amocrm._get_headers(),
                    params=params,
                    timeout=30,
                )
                if resp.status_code == 200:
                    return resp.json().get("_embedded", {}).get("contacts", []) or []
            logger.warning(f"[ENRICH] Contact fetch HTTP {resp.status_code}: {resp.text[:200]}")
            return []
        except Exception as exc:
            logger.error(f"[ENRICH] Contact fetch exception: {exc}")
            return []

    # -----------------------
    # Per-contact enrichment
    # -----------------------

    async def _enrich_contact(
        self,
        contact: Dict[str, Any],
        dry_run: bool,
    ) -> EnrichmentResult:
        contact_id = int(contact.get("id"))
        contact_name = contact.get("name") or f"Contact #{contact_id}"
        result = EnrichmentResult(contact_id=contact_id, contact_name=contact_name)

        text_corpus = self._build_contact_corpus(contact)
        usernames = extract_usernames(text_corpus)
        result.evidence.append(f"text_corpus_chars={len(text_corpus)}")

        if not usernames:
            result.status = "not_found"
            result.reason = "Contact yozuvlarida @username topilmadi"
            return result

        for username in usernames:
            try:
                phone, tg_id = await self._resolve_username(username)
            except Exception as exc:
                logger.warning(f"[ENRICH] Telethon error for @{username}: {exc}")
                result.status = "error"
                result.reason = f"Telegram lookup xatosi: {type(exc).__name__}"
                result.evidence.append(f"@{username} -> {exc}")
                continue

            result.found_username = username
            result.telegram_user_id = tg_id
            if phone:
                result.resolved_phone = phone
                result.status = "found"
                result.evidence.append(f"@{username} -> {phone}")
                break
            else:
                result.status = "hidden"
                result.reason = "Telegram raqamni yashirgan (privacy)"
                result.evidence.append(f"@{username} -> phone hidden")

        if result.resolved_phone:
            if dry_run:
                result.status = "dry_run"
                result.reason = "Dry-run: raqam topildi, lekin yozilmadi"
                return result
            applied = await asyncio.to_thread(
                self._patch_contact_phone, contact_id, result.resolved_phone
            )
            if applied:
                result.status = "applied"
                await self._tag_and_note(
                    contact_id,
                    ENRICHMENT_TAG,
                    self._format_enrichment_note(result),
                )
            else:
                result.status = "error"
                result.reason = "AmoCRM PATCH muvaffaqiyatsiz"
        else:
            await self._tag_and_note(
                contact_id,
                NO_PHONE_TAG,
                f"Oisha: telefon topib bo'lmadi. Tekshirilgan: {', '.join('@' + u for u in usernames)}",
            ) if not dry_run else None

        return result

    def _build_contact_corpus(self, contact: Dict[str, Any]) -> str:
        parts: List[str] = [str(contact.get("name") or "")]
        for field in contact.get("custom_fields_values") or []:
            parts.append(str(field.get("field_name") or ""))
            parts.append(str(field.get("field_code") or ""))
            for value in field.get("values") or []:
                parts.append(str(value.get("value") or ""))
        # Notes via existing API
        try:
            notes = self.amocrm._get_notes("contacts", int(contact.get("id"))) \
                if hasattr(self.amocrm, "_get_notes") else []
        except Exception:
            logger.error("Exception handled in %s", __name__, exc_info=True)
            notes = []
        for note in notes or []:
            params = note.get("params") or {}
            text = params.get("text") or params.get("message") or ""
            if text:
                parts.append(str(text)[:1500])
        return "\n".join(parts)

    # -----------------------
    # Telegram resolution
    # -----------------------

    async def _resolve_username(self, username: str) -> tuple[Optional[str], Optional[int]]:
        """Resolve a Telegram username to (phone, user_id).

        Uses get_entity for public users, then optionally ImportContactsRequest
        to try to reveal phone numbers. Telegram only shows the phone if the
        target user has phone visibility set to "Everybody" or already in our
        contacts.
        """
        if not self.tg_client:
            raise RuntimeError("Telegram client mavjud emas")

        from telethon.tl import functions, types  # type: ignore
        from telethon.errors import (
            UsernameNotOccupiedError,
            UsernameInvalidError,
            FloodWaitError,
        )

        try:
            entity = await self.tg_client.get_entity(username)
        except (UsernameNotOccupiedError, UsernameInvalidError):
            return None, None
        except FloodWaitError as fw:
            raise RuntimeError(f"Telegram flood-wait {fw.seconds}s") from fw

        if not isinstance(entity, types.User):
            return None, None

        tg_id = int(getattr(entity, "id", 0)) or None
        phone = getattr(entity, "phone", None)
        if phone:
            return normalize_phone(phone), tg_id

        # Try ImportContactsRequest as a probe — does NOT permanently store contact.
        try:
            imported = await self.tg_client(
                functions.contacts.ImportContactsRequest(
                    contacts=[
                        types.InputPhoneContact(
                            client_id=0,
                            phone="+998000000000",  # dummy probe, never used
                            first_name=getattr(entity, "first_name", "") or "x",
                            last_name=getattr(entity, "last_name", "") or "",
                        )
                    ]
                )
            )
            for user in getattr(imported, "users", []) or []:
                if user.id == entity.id and getattr(user, "phone", None):
                    # cleanup: delete the imported contact
                    try:
                        await self.tg_client(
                            functions.contacts.DeleteContactsRequest(id=[user])
                        )
                    except Exception:
                        logger.debug("[ENRICH] Failed to clean up imported Telegram contact", exc_info=True)
                    return normalize_phone(user.phone), tg_id
        except Exception as exc:
            logger.debug(f"[ENRICH] ImportContacts probe failed for @{username}: {exc}")

        return None, tg_id

    # -----------------------
    # AmoCRM writeback
    # -----------------------

    def _patch_contact_phone(self, contact_id: int, phone: str) -> bool:
        normalized = "+" + normalize_phone(phone) if not phone.startswith("+") else phone
        self.amocrm._load_token()
        url = f"{self.amocrm.base_url}/api/v4/contacts/{contact_id}"
        data = {
            "custom_fields_values": [
                {
                    "field_code": "PHONE",
                    "values": [{"value": normalized, "enum_code": "MOB"}],
                }
            ]
        }
        try:
            resp = requests.patch(
                url, headers=self.amocrm._get_headers(), json=data, timeout=30
            )
            if resp.status_code == 401 and self.amocrm.refresh_token():
                resp = requests.patch(
                    url, headers=self.amocrm._get_headers(), json=data, timeout=30
                )
            if resp.status_code in (200, 202):
                logger.info(f"[ENRICH OK] Contact {contact_id} -> {normalized}")
                return True
            logger.warning(
                f"[ENRICH] Contact {contact_id} PATCH failed: "
                f"{resp.status_code} {resp.text[:200]}"
            )
            return False
        except Exception as exc:
            logger.error(f"[ENRICH] Contact {contact_id} PATCH exception: {exc}")
            return False

    async def _tag_and_note(self, contact_id: int, tag: str, note: str) -> None:
        try:
            if hasattr(self.amocrm, "add_contact_tag"):
                await asyncio.to_thread(self.amocrm.add_contact_tag, contact_id, tag)
            await asyncio.to_thread(self.amocrm.add_contact_note, contact_id, note)
        except Exception as exc:
            logger.warning(f"[ENRICH] Tag/note failed for contact {contact_id}: {exc}")

    def _format_enrichment_note(self, result: EnrichmentResult) -> str:
        return (
            "Oisha Phone Enrichment\n"
            f"Topilgan @username: @{result.found_username}\n"
            f"Aniqlangan raqam: {result.resolved_phone}\n"
            f"Telegram user_id: {result.telegram_user_id}\n"
            f"Sana: {datetime.now(timezone.utc).isoformat()}\n"
            "AmoCRM dublikat birlashtirish funksiyasi bu nuqtadan keyin ishlaydi."
        )


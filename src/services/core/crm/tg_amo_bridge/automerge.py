"""Proactive Telegram-to-contact chat linking & duplicate Telegram deal auto-merger."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .amojo_client import AmoJoClient
from .analyzer import (
    LeadProfile,
    PairDecision,
    contact_phones,
    extract_phone_from_text,
    format_link_note,
    is_internal_team_phone,
    lead_tags,
    normalize_uz_phone,
    pick_best_pair,
    score_primary_lead,
)
from .executor import (
    MERGED_SOURCE_TAG,
    MERGED_TARGET_TAG,
    REVIEW_CONFLICT_TAG,
    execute_pair_decision,
    note_text,
)
from .store import MessageStore

logger = logging.getLogger("TgAmoBridge.automerge")

__all__ = [
    "LinkOutcome",
    "MERGED_SOURCE_TAG",
    "MERGED_TARGET_TAG",
    "REVIEW_CONFLICT_TAG",
    "TelegramDealAutoMerger",
    "_note_text",
]
_note_text = note_text


@dataclass
class LinkOutcome:
    status: str  # "cached" | "proactive_linked" | "merged" | "linked_only" | "conflict" | "not_resolved"
    phone: str = ""
    phone_source: str = ""
    amo_chat_id: Optional[str] = None
    target_contact_id: Optional[int] = None
    target_lead_id: Optional[int] = None
    merged_source_lead_id: Optional[int] = None
    reason: str = ""


def _contact_matches_username(contact: Dict[str, Any], username: str) -> bool:
    needle = username.lstrip("@").strip().lower()
    if len(needle) < 4:
        return False
    if needle in str(contact.get("name") or "").lower():
        return True
    for fld in contact.get("custom_fields_values") or []:
        for val in fld.get("values") or []:
            text = str(val.get("value") or "").lower()
            if f"@{needle}" in text or f"t.me/{needle}" in text or text.strip("@ ") == needle:
                return True
    return False


class TelegramDealAutoMerger:
    """Links Telegram chats to existing phone contacts and auto-merges duplicate TG deals."""

    def __init__(
        self,
        crm: Any,
        amojo: Optional[AmoJoClient],
        store: MessageStore,
        *,
        db: Optional[Any] = None,
        dry_run: bool = False,
        loss_reason_id: Optional[int] = None,
    ):
        self.crm = crm
        self.amojo = amojo
        self.store = store
        self.db = db
        self.dry_run = dry_run
        self.loss_reason_id = loss_reason_id

    async def resolve_client_phone(
        self,
        *,
        peer_id: int,
        sender_phone: Optional[str] = None,
        message_text: str = "",
        username: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Resolve a verified client phone from profile, chat text, cache, DB, or CRM username."""
        for raw, source in (
            (sender_phone, "telegram_profile"),
            (extract_phone_from_text(message_text), "message_text"),
        ):
            norm = normalize_uz_phone(raw)
            if norm and not is_internal_team_phone(norm):
                return norm, source

        cached = await self.store.get_chat_link(peer_id)
        if cached and cached.get("phone"):
            norm = normalize_uz_phone(cached["phone"])
            if norm and not is_internal_team_phone(norm):
                return norm, "cached_link"

        if self.db and hasattr(self.db, "get_user"):
            try:
                user = await self.db.get_user(peer_id)
                norm = normalize_uz_phone((user or {}).get("phone"))
                if norm and not is_internal_team_phone(norm):
                    return norm, "oisha_db"
            except Exception as exc:
                logger.debug("[TG-MERGE] db.get_user failed: %s", type(exc).__name__)

        if username and self.crm and hasattr(self.crm, "find_contacts_by_query_async"):
            contacts = await self.crm.find_contacts_by_query_async(username.lstrip("@"))
            for contact in contacts:
                if _contact_matches_username(contact, username):
                    phones = contact_phones(contact)
                    if phones and not is_internal_team_phone(phones[0]):
                        return phones[0], "amocrm_username"
        return "", ""

    async def build_profiles_for_contact(
        self, contact: Dict[str, Any], *, chat_linked: Optional[bool] = None
    ) -> List[LeadProfile]:
        """Build LeadProfile objects for all leads linked to a single contact."""
        cid = int(contact["id"])
        phones = contact_phones(contact)
        lead_refs = (contact.get("_embedded") or {}).get("leads") or []
        if not lead_refs and hasattr(self.crm, "get_contact_linked_leads"):
            lead_refs = await self.crm.get_contact_linked_leads(cid)
        if not lead_refs:
            return []

        call_count = (
            await self.crm.get_contact_call_notes_count(cid)
            if hasattr(self.crm, "get_contact_call_notes_count")
            else 0
        )
        has_chat = (
            chat_linked
            if chat_linked is not None
            else (bool(await self.crm.get_contact_chats(contact_id=cid)) if hasattr(self.crm, "get_contact_chats") else False)
        )
        profiles: List[LeadProfile] = []
        for ref in lead_refs:
            lid = int(ref.get("id") or 0)
            lead = await self.crm.get_lead(lid) if lid > 0 else None
            if not lead:
                continue
            notes = await self.crm.get_lead_notes(lid) if hasattr(self.crm, "get_lead_notes") else []
            profiles.append(
                LeadProfile(
                    lead_id=lid,
                    contact_id=cid,
                    name=str(lead.get("name") or ""),
                    status_id=int(lead.get("status_id") or 0),
                    pipeline_id=int(lead.get("pipeline_id") or 0),
                    price=int(lead.get("price") or 0),
                    created_at=int(lead.get("created_at") or 0),
                    updated_at=int(lead.get("updated_at") or 0),
                    call_count=call_count,
                    has_chat=bool(has_chat),
                    notes_count=len(notes),
                    tags=lead_tags(lead),
                    phones=phones,
                )
            )
        return profiles

    async def _pick_target(
        self, contacts: List[Dict[str, Any]]
    ) -> Tuple[Optional[Dict[str, Any]], Optional[LeadProfile], List[LeadProfile]]:
        all_profiles: List[LeadProfile] = []
        by_id = {int(c["id"]): c for c in contacts if c.get("id")}
        for contact in contacts:
            all_profiles.extend(await self.build_profiles_for_contact(contact))
        if all_profiles:
            ranked = sorted(
                all_profiles,
                key=lambda p: (score_primary_lead(p)[0], -(p.created_at or 0)),
                reverse=True,
            )
            best = ranked[0]
            return by_id.get(best.contact_id, contacts[0]), best, all_profiles
        ordered = sorted(contacts, key=lambda c: int(c.get("created_at") or 0))
        return ordered[0] if ordered else None, None, []

    async def _ensure_amo_chat_id(
        self,
        *,
        peer_id: int,
        cached_chat_id: Optional[str],
        client_name: str,
        phone: str,
        username: Optional[str],
        source_external_id: Optional[str],
    ) -> Optional[str]:
        if cached_chat_id:
            return cached_chat_id
        if not (self.amojo and hasattr(self.amojo, "create_chat")):
            return None
        profile_link = f"https://t.me/{username.lstrip('@')}" if username else None
        return await self.amojo.create_chat(
            conversation_id=str(peer_id),
            user_id=str(peer_id),
            user_name=client_name,
            phone=f"+{phone}",
            profile_link=profile_link,
            source_external_id=source_external_id,
        )

    async def _collect_split_candidates(
        self, current_cids: set[int], target_cid: int, phone_profiles: List[LeadProfile]
    ) -> List[LeadProfile]:
        candidates = list(phone_profiles)
        seen_lids = {p.lead_id for p in candidates}
        for existing_cid in current_cids:
            if existing_cid == target_cid:
                continue
            details = await self.crm.get_contact_details_async(existing_cid)
            if not details:
                continue
            for prof in await self.build_profiles_for_contact(details, chat_linked=True):
                if prof.lead_id not in seen_lids:
                    candidates.append(prof)
                    seen_lids.add(prof.lead_id)
        return candidates

    async def _reconcile_existing_chat_contacts(
        self,
        *,
        current_cids: set[int],
        target_cid: int,
        target_lid: Optional[int],
        phone_profiles: List[LeadProfile],
        phone: str,
        phone_source: str,
        amo_chat_id: Optional[str],
        peer_id: int,
        username: Optional[str],
    ) -> LinkOutcome:
        candidates = await self._collect_split_candidates(current_cids, target_cid, phone_profiles)
        decision = pick_best_pair(candidates)
        if decision and decision.action in {"merge", "link_only", "conflict"}:
            status = await self.execute_decision(
                decision, phone=phone, amo_chat_id=amo_chat_id, tg_user_id=peer_id, username=username
            )
            await self.store.upsert_chat_link(
                peer_id, amo_chat_id=amo_chat_id, phone=phone, username=username,
                linked_contact_id=decision.target_contact_id, linked_lead_id=decision.target_lead_id,
            )
            return LinkOutcome(
                status, phone, phone_source, amo_chat_id,
                decision.target_contact_id, decision.target_lead_id,
                decision.source_lead_id if status == "merged" else None, decision.reason,
            )
        if target_cid not in current_cids and amo_chat_id and not self.dry_run:
            await self.crm.link_chat_to_contact(target_cid, amo_chat_id)
        await self.store.upsert_chat_link(
            peer_id, amo_chat_id=amo_chat_id, phone=phone, username=username,
            linked_contact_id=target_cid, linked_lead_id=target_lid,
        )
        return LinkOutcome("proactive_linked", phone, phone_source, amo_chat_id, target_cid, target_lid)

    async def _bind_new_chat(
        self,
        *,
        peer_id: int,
        target_cid: int,
        target_lid: Optional[int],
        amo_chat_id: Optional[str],
        phone: str,
        phone_source: str,
        username: Optional[str],
        client_name: str,
    ) -> LinkOutcome:
        if not self.dry_run and amo_chat_id:
            if await self.crm.link_chat_to_contact(target_cid, amo_chat_id) and target_lid:
                await self.crm.add_lead_note_async(
                    target_lid,
                    format_link_note(
                        phone=phone, phone_source=phone_source,
                        tg_user_id=peer_id, username=username, client_name=client_name,
                    ),
                )
        await self.store.upsert_chat_link(
            peer_id, amo_chat_id=amo_chat_id, phone=phone, username=username,
            linked_contact_id=target_cid, linked_lead_id=target_lid,
        )
        return LinkOutcome("proactive_linked", phone, phone_source, amo_chat_id, target_cid, target_lid)

    @staticmethod
    def _cached_outcome(cached: Optional[dict], phone: str, phone_source: str, force_recheck: bool) -> Optional[LinkOutcome]:
        if (
            not force_recheck
            and cached
            and cached.get("linked_contact_id")
            and cached.get("phone") == phone
            and phone_source != "message_text"
        ):
            return LinkOutcome(
                "cached",
                phone=phone,
                phone_source=phone_source,
                amo_chat_id=cached.get("amo_chat_id"),
                target_contact_id=cached.get("linked_contact_id"),
                target_lead_id=cached.get("linked_lead_id"),
            )
        return None

    async def ensure_chat_linked_before_send(
        self,
        *,
        peer_id: int,
        client_name: str,
        sender_phone: Optional[str] = None,
        message_text: str = "",
        username: Optional[str] = None,
        source_external_id: Optional[str] = None,
        force_recheck: bool = False,
    ) -> LinkOutcome:
        """Link chat to existing phone contact before send_event; merge if already split."""
        if not self.crm:
            return LinkOutcome("not_resolved", reason="crm_unavailable")

        cached = await self.store.get_chat_link(peer_id)
        phone, phone_source = await self.resolve_client_phone(
            peer_id=peer_id, sender_phone=sender_phone, message_text=message_text, username=username
        )
        if not phone:
            await self.store.upsert_chat_link(peer_id, username=username)
            return LinkOutcome("not_resolved", reason="phone_not_found")

        fast = self._cached_outcome(cached, phone, phone_source, force_recheck)
        if fast is not None:
            return fast
        contacts = await self.crm.find_contacts_by_phone_async(phone)
        if not contacts:
            await self.store.upsert_chat_link(peer_id, phone=phone, username=username)
            return LinkOutcome("not_resolved", phone=phone, phone_source=phone_source, reason="no_crm_contact")
        target_contact, target_lead, phone_profiles = await self._pick_target(contacts)
        if not target_contact:
            return LinkOutcome("not_resolved", phone=phone, phone_source=phone_source, reason="no_target")
        target_cid, target_lid = int(target_contact["id"]), (target_lead.lead_id if target_lead else None)

        amo_chat_id = await self._ensure_amo_chat_id(
            peer_id=peer_id, cached_chat_id=(cached or {}).get("amo_chat_id"),
            client_name=client_name, phone=phone, username=username, source_external_id=source_external_id,
        )
        existing_links = (
            await self.crm.get_contact_chats(chat_id=amo_chat_id)
            if amo_chat_id and hasattr(self.crm, "get_contact_chats") else []
        )
        current_cids = {int(r["contact_id"]) for r in existing_links if r.get("contact_id")}
        common = dict(
            target_cid=target_cid, target_lid=target_lid, phone=phone,
            phone_source=phone_source, amo_chat_id=amo_chat_id, peer_id=peer_id, username=username,
        )
        if current_cids:
            return await self._reconcile_existing_chat_contacts(
                current_cids=current_cids, phone_profiles=phone_profiles, **common
            )
        return await self._bind_new_chat(client_name=client_name, **common)

    async def execute_decision(
        self,
        decision: PairDecision,
        *,
        phone: str,
        amo_chat_id: Optional[str] = None,
        tg_user_id: Optional[int] = None,
        username: Optional[str] = None,
    ) -> str:
        """Delegate decision execution to the idempotent executor module."""
        return await execute_pair_decision(
            self.crm,
            self.store,
            decision,
            phone=phone,
            amo_chat_id=amo_chat_id,
            tg_user_id=tg_user_id,
            username=username,
            dry_run=self.dry_run,
            loss_reason_id=self.loss_reason_id,
        )

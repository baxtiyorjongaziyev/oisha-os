"""
Non-client detection and suppression module.

Filters out contacts and deals marked as "mijoz emas" (non-client, spam,
relative, rejected, etc.) across deal names, contact names, notes, task
responses, and chat messages. Prevents task creation and blocks re-import
into CRM/chat.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("NonClientFilter")

# Cache to prevent repeated AmoCRM API round-trips: key -> (is_non_client, reason, expiry_time)
_NON_CLIENT_CACHE: Dict[str, Tuple[bool, str, float]] = {}
_CACHE_TTL_SECONDS = 1800.0  # 30 minutes


# Regex patterns matching various forms of "mijoz emas", "not client", "spam", etc.
_NON_CLIENT_PATTERNS: List[Tuple[re.Pattern, str]] = [
    # Uzbek: mijoz emas, mijozmas, klient emas, klientmas
    (re.compile(r"\b(?:mijoz|klient|client)\s*(?:emas|mas|emasdir|emaslik)\b", re.IGNORECASE), "mijoz_emas"),
    (re.compile(r"\b(?:мижоз|клиент)\s*(?:эмас|мас|эмасдир)\b", re.IGNORECASE), "mijoz_emas_cyrillic"),
    # Russian: не клиент, нецелевой, не целевой
    (re.compile(r"\bне\s*клиент\b", re.IGNORECASE), "ne_klient"),
    (re.compile(r"\bне\s*целев(?:ой|ая|ое|ые|ую)\b", re.IGNORECASE), "ne_celevoy"),
    (re.compile(r"\bнецелев(?:ой|ая|ое|ые|ую)\b", re.IGNORECASE), "necelevoy"),
    # English: not a client, not client, non-client
    (re.compile(r"\bnot\s+a?\s*client\b", re.IGNORECASE), "not_client"),
    (re.compile(r"\bnon[-_\s]?client\b", re.IGNORECASE), "non_client"),
    # Spam, adashgan, wrong number
    (re.compile(r"\b(?:adashgan|adashib\s*tushgan|adashib|adashgan\s*lid)\b", re.IGNORECASE), "adashgan"),
    (re.compile(r"\b(?:noto['\u2019`]?g['\u2019`]?ri\s*raqam|wrong\s*number)\b", re.IGNORECASE), "wrong_number"),
    (re.compile(r"\b(?:spam|спам|reklama|реклама)\b", re.IGNORECASE), "spam_or_ads"),
    # Rejection: kerak emas, qiziqmadi, rad etdi, otkaz
    (re.compile(r"\b(?:kerak\s*emas|keremas|kerakmas)\b", re.IGNORECASE), "kerak_emas"),
    (re.compile(r"\b(?:xizmat\s*kerak\s*emas|kerak\s*bo['\u2019`]?lmaydi)\b", re.IGNORECASE), "xizmat_kerak_emas"),
    (re.compile(r"\b(?:qiziqmadi|qiziqmaydi|qiziqish\s*yo['\u2019`]?q)\b", re.IGNORECASE), "qiziqmadi"),
    (re.compile(r"\b(?:rad\s*etdi|rad\s*qildi|otkaz\s*qildi|отказ|отказался|отказалась)\b", re.IGNORECASE), "rad_etdi"),
    (re.compile(r"\bнет\s*потребности\b", re.IGNORECASE), "net_potrebnosti"),
    # Personal / internal connections: shaxsiy, oila, tanish, ustoz, sherik, hamkor, xodim
    (re.compile(r"\b(?:shaxsiy\s*kontakt|shaxsiy\s*tanish|oila\s*a['\u2019`]?zosi|qarindosh)\b", re.IGNORECASE), "personal_or_family"),
    (re.compile(r"\b(?:hamkor|sherik|xodim|ustoz)\b", re.IGNORECASE), "internal_or_partner"),
]


def is_text_marked_as_non_client(text: Optional[str]) -> Tuple[bool, str]:
    """
    Checks if a given string contains explicit 'mijoz emas' markers.
    Returns (True, reason) if matched, otherwise (False, "").
    """
    if not text:
        return False, ""
    clean = str(text).strip()
    if not clean:
        return False, ""

    for pattern, reason in _NON_CLIENT_PATTERNS:
        if pattern.search(clean):
            return True, reason
    return False, ""


def _check_cache(key: str) -> Optional[Tuple[bool, str]]:
    cached = _NON_CLIENT_CACHE.get(key)
    if cached:
        is_nc, reason, expiry = cached
        if time.time() < expiry:
            return is_nc, reason
        _NON_CLIENT_CACHE.pop(key, None)
    return None


def _set_cache(key: str, is_nc: bool, reason: str) -> None:
    _NON_CLIENT_CACHE[key] = (is_nc, reason, time.time() + _CACHE_TTL_SECONDS)


async def is_lead_marked_as_non_client(
    amocrm_sync: Any,
    lead_id: int,
    lead_data: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, str]:
    """
    Checks deal name, tags, linked contacts, notes, and tasks for 'mijoz emas'.
    Returns (True, reason) if non-client, (False, "") if valid customer.
    """
    cache_key = f"lead_{lead_id}"
    cached = _check_cache(cache_key)
    if cached is not None:
        return cached

    lead = lead_data
    if not lead and amocrm_sync:
        lead = await amocrm_sync.get_lead(lead_id)

    if not lead:
        return False, ""

    # 1. Check deal name
    lead_name = lead.get("name") or ""
    matched, reason = is_text_marked_as_non_client(lead_name)
    if matched:
        _set_cache(cache_key, True, f"sdelka_nomi: {reason}")
        return True, f"sdelka_nomi ({reason})"

    # 2. Check tags
    tags = lead.get("_embedded", {}).get("tags", []) or lead.get("tags", [])
    for tag in tags:
        tag_name = tag.get("name") if isinstance(tag, dict) else str(tag)
        matched, reason = is_text_marked_as_non_client(tag_name)
        if matched:
            _set_cache(cache_key, True, f"tag: {reason}")
            return True, f"tag ({reason})"

    # 3. Check linked contacts
    contacts = lead.get("_embedded", {}).get("contacts", [])
    for c in contacts:
        c_name = c.get("name") or ""
        matched, reason = is_text_marked_as_non_client(c_name)
        if matched:
            _set_cache(cache_key, True, f"mijoz_nomi: {reason}")
            return True, f"mijoz_nomi ({reason})"

    # 4. Check primechaniya (notes) & chat messages
    if amocrm_sync and hasattr(amocrm_sync, "get_lead_notes"):
        try:
            notes = await amocrm_sync.get_lead_notes(lead_id)
            for n in notes:
                params = n.get("params") or {}
                note_text = params.get("text") or n.get("text") or ""
                matched, reason = is_text_marked_as_non_client(note_text)
                if matched:
                    _set_cache(cache_key, True, f"primechaniya: {reason}")
                    return True, f"primechaniya ({reason})"
        except Exception as exc:
            logger.debug("[NON_CLIENT] Lead %s notes check failed: %s", lead_id, exc)

    # 5. Check tasks & task responses (results)
    if amocrm_sync and hasattr(amocrm_sync, "get_lead_tasks"):
        try:
            tasks = await amocrm_sync.get_lead_tasks(lead_id)
            for t in tasks:
                t_text = t.get("text") or ""
                matched, reason = is_text_marked_as_non_client(t_text)
                if matched:
                    _set_cache(cache_key, True, f"zadacha: {reason}")
                    return True, f"zadacha ({reason})"
                result = t.get("result") or {}
                res_text = result.get("text") if isinstance(result, dict) else ""
                matched, reason = is_text_marked_as_non_client(res_text)
                if matched:
                    _set_cache(cache_key, True, f"zadachaga_javob: {reason}")
                    return True, f"zadachaga_javob ({reason})"
        except Exception as exc:
            logger.debug("[NON_CLIENT] Lead %s tasks check failed: %s", lead_id, exc)

    _set_cache(cache_key, False, "")
    return False, ""


async def is_sender_marked_as_non_client(
    amocrm_sync: Any,
    phone: Optional[str] = None,
    user_id: Optional[int] = None,
    name: Optional[str] = None,
    db: Optional[Any] = None,
) -> Tuple[bool, str]:
    """
    Checks if an incoming sender is marked as non-client.
    Prevents opening new CRM deals and pushing messages into CRM chat.
    """
    if name:
        matched, reason = is_text_marked_as_non_client(name)
        if matched:
            return True, f"sender_name ({reason})"

    cache_key = f"sender_{user_id or phone}"
    cached = _check_cache(cache_key)
    if cached is not None:
        return cached

    if db and user_id and hasattr(db, "get_user"):
        try:
            db_user = await db.get_user(user_id)
            if db_user:
                u_intent = str(db_user.get("intent") or "").upper()
                if u_intent in {"NON_CLIENT", "SPAM", "PERSONAL"}:
                    _set_cache(cache_key, True, f"db_intent_{u_intent.lower()}")
                    return True, f"db_intent ({u_intent})"
        except Exception as exc:
            logger.debug("[NON_CLIENT] DB user check failed: %s", exc)

    if amocrm_sync and phone:
        try:
            contact = None
            if hasattr(amocrm_sync, "get_contact_by_phone"):
                res = amocrm_sync.get_contact_by_phone(phone)
                import inspect
                contact = await res if inspect.isawaitable(res) else res
            elif hasattr(amocrm_sync, "find_contact_by_phone"):
                contact = amocrm_sync.find_contact_by_phone(phone)

            if contact:
                c_name = contact.get("name") or ""
                matched, reason = is_text_marked_as_non_client(c_name)
                if matched:
                    _set_cache(cache_key, True, f"amocrm_contact_name: {reason}")
                    return True, f"amocrm_contact ({reason})"

                if hasattr(amocrm_sync, "get_notes"):
                    notes = await amocrm_sync.get_notes("contacts", entity_id=contact["id"], limit=10)
                    for n in notes:
                        n_text = (n.get("params") or {}).get("text") or n.get("text") or ""
                        matched, reason = is_text_marked_as_non_client(n_text)
                        if matched:
                            _set_cache(cache_key, True, f"contact_primechaniya: {reason}")
                            return True, f"contact_primechaniya ({reason})"
        except Exception as exc:
            logger.debug("[NON_CLIENT] AmoCRM contact check failed: %s", exc)

    _set_cache(cache_key, False, "")
    return False, ""


def clear_non_client_cache() -> None:
    """Clear internal cache (useful for tests and manual resets)."""
    _NON_CLIENT_CACHE.clear()

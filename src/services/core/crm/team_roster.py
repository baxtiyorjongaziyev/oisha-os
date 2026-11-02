"""Canonical Team Roster & Single Source of Truth (SSoT) for Jon Branding Agency.

Provides a unified, SQLite-backed (`data/crm_dialer.db`) and canonically seeded
registry of all active staff members, their roles, Telegram IDs/handles,
AmoCRM responsible IDs, Airtable record IDs, and Moizvonki telephony emails.
Explicitly blocks known non-staff/client names (e.g., Dilnoza Muminova) and
former employees (e.g., Farangiz, Oydin) from being treated as active staff.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import logging
import os
import sqlite3
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = "data/crm_dialer.db"

# Explicitly excluded former staff and client names that must never be treated as active staff
EXCLUDED_NON_STAFF_SLUGS: Set[str] = {
    "farangiz",
    "oydin",
    "dilnoza",
    "dilnoza_muminova",
}


@dataclass(frozen=True)
class StaffMember:
    slug: str
    name: str
    role: str  # admin, seller, specialist, finance, designer, marketing
    title: str
    tg_user_id: Optional[int] = None
    tg_username: str = ""
    phone: str = ""
    amocrm_user_id: Optional[int] = None
    moizvonki_emails: Tuple[str, ...] = field(default_factory=tuple)
    airtable_record_id: Optional[str] = None
    aliases: Tuple[str, ...] = field(default_factory=tuple)
    active: bool = True

    def tg_markdown_mention(self) -> str:
        """Return Markdown mention link `[Name](tg://user?id=...)` (+ @handle if present)."""
        base = f"[{self.name}](tg://user?id={self.tg_user_id})" if self.tg_user_id else self.name
        if self.tg_username:
            handle = self.tg_username if self.tg_username.startswith("@") else f"@{self.tg_username}"
            return f"{base} ({handle})"
        return base

    def tg_html_mention(self) -> str:
        """Return HTML mention link `<a href="tg://user?id=...">Name</a>`."""
        if self.tg_user_id:
            return f'<a href="tg://user?id={self.tg_user_id}">{self.name}</a>'
        if self.tg_username:
            return self.tg_username if self.tg_username.startswith("@") else f"@{self.tg_username}"
        return self.name


# Canonical Verified Staff Roster (2026-10-31)
CANONICAL_STAFF: Tuple[StaffMember, ...] = (
    StaffMember(
        slug="baxtiyorjon",
        name="Baxtiyorjon Gaziyev",
        role="admin",
        title="Rahbar (Owner & CEO)",
        tg_user_id=150074828,
        tg_username="@baxtiyorjongaziyev",
        phone="+998336450097",
        amocrm_user_id=8128012,
        moizvonki_emails=("jonbranding@agency.uz",),
        airtable_record_id="reccXjZIGIcRezKgB",
        aliases=("baxtiyorjon", "baxtiyor"),
    ),
    StaffMember(
        slug="shahnoza",
        name="Shahnoza Abdijabborova",
        role="seller",
        title="Biznes assistent va sotuv menejeri",
        tg_user_id=8802892610,
        tg_username="@jonbranding_assistant",
        phone="+998773220042",
        amocrm_user_id=13021974,
        moizvonki_emails=("shahnoza@jonbranding.uz",),
        airtable_record_id="rec8fmSHRpZi5Rx9N",
        aliases=("shahnoza", "shaxnoza", "shahnoza xayrullayevna", "shahnozzy"),
    ),
    StaffMember(
        slug="rayxona",
        name="Rayxona Rahimova",
        role="seller",
        title="Sotuv menejeri (Closer)",
        tg_user_id=8878762085,
        tg_username="@RayxonJonbranding",
        phone="+998777411397",
        amocrm_user_id=9000001,
        moizvonki_emails=("rayxona@jonbranding.uz", "xayrullayevna006@gmail.com"),
        aliases=("rayxona", "rayxon", "rayhona", "rayxonjonbranding"),
    ),
    StaffMember(
        slug="mumtozmaxal",
        name="Mumtozmaxal Normurodova",
        role="seller",
        title="Sotuv menejeri (Closer)",
        tg_user_id=8940413540,
        tg_username="@MumtozmaxalJonbranding",
        phone="+998773220098",
        amocrm_user_id=9000002,
        moizvonki_emails=("mumtozmaxal@jonbranding.uz",),
        aliases=("mumtozmaxal", "mumtozmahal", "mumtoz", "mumtozmaxaljonbranding"),
    ),
    StaffMember(
        slug="hasanboy",
        name="Hasanboy Gaziyev",
        role="specialist",
        title="Patent va brend himoyasi mutaxassisi",
        tg_user_id=8090679294,
        tg_username="@hasan_yahyo",
        phone="+998973355900",
        amocrm_user_id=9000003,
        airtable_record_id="recPi9SROzJNK8SX7",
        aliases=("hasanboy", "hasan", "hasan_yahyo"),
    ),
    StaffMember(
        slug="ifora",
        name="Ifora",
        role="specialist",
        title="Loyiha menejeri (PM)",
        tg_user_id=5748052638,
        aliases=("ifora",),
    ),
    StaffMember(
        slug="ahroriy",
        name="Ahroriy Abdulloh",
        role="marketing",
        title="Targetolog va marketing mutaxassisi",
        tg_user_id=1704424936,
        airtable_record_id="recp8ClrBsXi6G0Km",
        aliases=("ahroriy", "ahrorbek", "ahror", "abdulloh"),
    ),
    StaffMember(
        slug="beslan",
        name="Beslan",
        role="designer",
        title="Dizayner",
        tg_user_id=7005708460,
        aliases=("beslan", "беслан"),
    ),
    StaffMember(
        slug="dilbar",
        name="Dilbar",
        role="finance",
        title="Moliyachi (Hisobchi)",
        tg_user_id=8611068511,
        aliases=("dilbar", "dilbar akbarovna"),
    ),
)

_BY_SLUG: Dict[str, StaffMember] = {m.slug: m for m in CANONICAL_STAFF}


def get_active_staff(
    *,
    include_owner: bool = True,
    roles: Optional[Iterable[str]] = None,
    db_path: str = DEFAULT_DB_PATH,
) -> List[StaffMember]:
    """Return active staff members merged with any dynamic updates in `crm_seller_accounts`."""
    role_filter = {r.lower() for r in roles} if roles else None
    db_overrides = _read_db_overrides(db_path)

    members: List[StaffMember] = []
    for m in CANONICAL_STAFF:
        if not m.active:
            continue
        if not include_owner and m.role == "admin":
            continue
        if role_filter and m.role.lower() not in role_filter:
            continue
        override = db_overrides.get(m.slug)
        if override:
            m = StaffMember(
                slug=m.slug,
                name=override.get("name") or m.name,
                role=override.get("role") or m.role,
                title=m.title,
                tg_user_id=override.get("tg_user_id") or m.tg_user_id,
                tg_username=override.get("tg") or m.tg_username,
                phone=override.get("phone") or m.phone,
                amocrm_user_id=override.get("rep_id") or m.amocrm_user_id,
                moizvonki_emails=m.moizvonki_emails,
                airtable_record_id=m.airtable_record_id,
                aliases=m.aliases,
                active=m.active,
            )
        members.append(m)
    return members


def _read_db_overrides(db_path: str = DEFAULT_DB_PATH) -> Dict[str, Dict[str, Any]]:
    if not db_path or not os.path.exists(db_path):
        return {}
    try:
        conn = sqlite3.connect(db_path, timeout=3.0)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT slug, name, rep_id, phone, tg, role FROM crm_seller_accounts").fetchall()
        conn.close()
        result: Dict[str, Dict[str, Any]] = {}
        for r in rows:
            slug = str(r["slug"] or "").strip().lower()
            if slug and slug not in EXCLUDED_NON_STAFF_SLUGS:
                result[slug] = dict(r)
        return result
    except Exception as exc:
        logger.debug("[ROSTER] Optional DB override read skipped: %s", exc)
        return {}


def find_staff(identifier: Optional[str | int], db_path: str = DEFAULT_DB_PATH) -> Optional[StaffMember]:
    """Lookup an active staff member by slug, name, alias, Telegram ID, @username, or email."""
    if identifier is None:
        return None
    raw = str(identifier).strip()
    if not raw:
        return None
    clean = raw.lstrip("@").lower()
    if clean in EXCLUDED_NON_STAFF_SLUGS or "dilnoza" in clean:
        return None

    for m in get_active_staff(include_owner=True, db_path=db_path):
        if clean == m.slug or clean == m.name.lower():
            return m
        if m.tg_user_id is not None and clean == str(m.tg_user_id):
            return m
        if m.amocrm_user_id is not None and clean == str(m.amocrm_user_id):
            return m
        if m.tg_username and clean == m.tg_username.lstrip("@").lower():
            return m
        if any(clean == em.lower() or clean == em.split("@")[0].lower() for em in m.moizvonki_emails):
            return m
        if any(clean == al.lower() for al in m.aliases):
            return m
        first_token = clean.split()[0]
        if first_token in m.aliases or first_token == m.slug:
            return m
    return None


def get_moizvonki_rep_map(db_path: str = DEFAULT_DB_PATH) -> Dict[str, Dict[str, Any]]:
    """Return mapping of `moizvonki_email -> {slug, name, rep_id, tg}` for active staff."""
    mapping: Dict[str, Dict[str, Any]] = {}
    for m in get_active_staff(include_owner=True, db_path=db_path):
        for email in m.moizvonki_emails:
            mapping[email.lower()] = {
                "slug": m.slug,
                "name": m.name,
                "rep_id": m.amocrm_user_id,
                "tg": m.tg_username,
                "tg_user_id": m.tg_user_id,
            }
    return mapping


def get_moizvonki_rep_names(include_owner: bool = False, db_path: str = DEFAULT_DB_PATH) -> Dict[str, str]:
    """Return `email -> Short Display Name` for daily/hourly call reports."""
    names: Dict[str, str] = {}
    for m in get_active_staff(include_owner=include_owner, roles=("seller", "admin"), db_path=db_path):
        if not include_owner and m.role == "admin":
            continue
        short_name = m.name if m.slug == "shahnoza" else m.name.split()[0]
        for email in m.moizvonki_emails:
            if email.endswith("@jonbranding.uz") or not names:
                names[email.lower()] = short_name
    return names


def get_rep_tg_usernames(db_path: str = DEFAULT_DB_PATH) -> Dict[str, str]:
    """Return normalized first-name/alias -> `@username` for sales reps."""
    res: Dict[str, str] = {}
    for m in get_active_staff(include_owner=False, roles=("seller",), db_path=db_path):
        if not m.tg_username:
            continue
        res[m.slug] = m.tg_username
        res[m.name.split()[0].lower()] = m.tg_username
        for al in m.aliases:
            res[al.lower()] = m.tg_username
    return res


def get_known_manager_tags(db_path: str = DEFAULT_DB_PATH) -> Set[str]:
    """Return lowercase manager names/aliases for AmoCRM lead claim detection."""
    tags: Set[str] = set()
    for m in get_active_staff(include_owner=True, db_path=db_path):
        tags.add(m.slug.lower())
        tags.add(m.name.lower())
        tags.add(m.name.split()[0].lower())
        for al in m.aliases:
            tags.add(al.lower())
    return tags - EXCLUDED_NON_STAFF_SLUGS


def format_hermes_roster_markdown(include_owner: bool = False, db_path: str = DEFAULT_DB_PATH) -> str:
    """Format active team members as bulleted Markdown mention lines for Hermes prompts."""
    lines = []
    for m in get_active_staff(include_owner=include_owner, db_path=db_path):
        lines.append(f"• {m.tg_markdown_mention()} — {m.title}")
    return "\n".join(lines)


def find_staff_by_tags(tags: Iterable[str], db_path: str = DEFAULT_DB_PATH) -> Optional[StaffMember]:
    """Identify assigned sales manager based on AmoCRM lead tags (single-account license model)."""
    if not tags:
        return None
    for tag in tags:
        clean = str(tag).strip()
        matched = find_staff(clean, db_path=db_path)
        if matched and matched.role in ("seller", "admin"):
            return matched
    return None


def get_lead_assigned_seller(lead: Dict[str, Any], db_path: str = DEFAULT_DB_PATH) -> Optional[StaffMember]:
    """Extract lead tags and resolve the assigned seller StaffMember."""
    raw_tags = (lead.get("_embedded") or {}).get("tags") or lead.get("tags") or []
    tag_names = [t.get("name") if isinstance(t, dict) else str(t) for t in raw_tags]
    return find_staff_by_tags(tag_names, db_path=db_path)


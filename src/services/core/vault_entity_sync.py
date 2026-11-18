"""
24/7 Vault Entity Sync for Oisha-OS.

Keeps `70-Odamlar/` and `70-AmoCRM/` in the Obsidian Second Brain vault
in sync with incoming events from Telegram, amoCRM, Airtable, Telefon,
and Instagram without creating duplicate person notes.
"""

import datetime
import logging
import re
from pathlib import Path
from typing import Iterable, Optional

import yaml

from src.services.core.second_brain_sync import _sanitize_filename, resolve_vault_path

logger = logging.getLogger("VaultEntitySync")


def _norm_phone(phone: Optional[str]) -> Optional[str]:
    if not phone:
        return None
    digits = re.sub(r"\D", "", str(phone))
    return digits[-9:] if len(digits) >= 9 else None


def _norm_tg(username: Optional[str]) -> Optional[str]:
    if not username:
        return None
    clean = str(username).strip().lstrip("@").lower()
    return clean or None


def _read_note(path: Path) -> tuple[dict, str]:
    text = path.read_bytes().decode("utf-8-sig", errors="replace").replace("\r\n", "\n")
    if text.startswith("---\n"):
        parts = text.split("\n---\n", 1)
        if len(parts) == 2:
            try:
                return (yaml.safe_load(parts[0][4:]) or {}), parts[1]
            except Exception:
                return {}, text
    return {}, text


def _write_note(path: Path, fm: dict, body: str) -> None:
    fm_str = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False, default_flow_style=False).strip()
    content = f"---\n{fm_str}\n---\n{body}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _find_person_note(odamlar_dir: Path, phone: Optional[str], telegram: Optional[str], name: str) -> Optional[Path]:
    np = _norm_phone(phone)
    nt = _norm_tg(telegram)
    if np or nt:
        for md in odamlar_dir.glob("*.md"):
            fm, _ = _read_note(md)
            phones = fm.get("telefon") or []
            if isinstance(phones, (str, int)):
                phones = [phones]
            if np and any(_norm_phone(p) == np for p in phones):
                return md
            tgs = fm.get("telegram") or []
            if isinstance(tgs, str):
                tgs = [tgs]
            if nt and any(_norm_tg(t) == nt for t in tgs):
                return md
    candidate = odamlar_dir / f"{_sanitize_filename(name, max_len=60)}.md"
    return candidate if candidate.exists() else None


def sync_person_to_vault(
    name: str,
    phone: Optional[str] = None,
    telegram: Optional[str] = None,
    tags: Optional[Iterable[str]] = None,
    source: str = "Oisha-OS",
    vault_path: Optional[Path] = None,
) -> Optional[Path]:
    """Create or update a person note in `70-Odamlar/` without duplicates."""
    vault = vault_path or resolve_vault_path()
    if not vault:
        return None
    odamlar_dir = vault / "70-Odamlar"
    odamlar_dir.mkdir(parents=True, exist_ok=True)

    existing = _find_person_note(odamlar_dir, phone, telegram, name)
    target = existing or (odamlar_dir / f"{_sanitize_filename(name, max_len=60)}.md")
    fm, body = _read_note(target) if target.exists() else ({"type": "odam", "nom": name}, f"\n# {name}\n")

    if phone:
        phones = list(fm.get("telefon") or [])
        np = _norm_phone(phone)
        if np and not any(_norm_phone(p) == np for p in phones):
            phones.append(str(phone).strip())
        fm["telefon"] = phones

    if telegram:
        tgs = list(fm.get("telegram") or [])
        nt = _norm_tg(telegram)
        if nt and not any(_norm_tg(t) == nt for t in tgs):
            tgs.append(f"@{nt}")
        fm["telegram"] = tgs

    tag_list = list(fm.get("tags") or ["odam"])
    for t in tags or []:
        if t and t not in tag_list:
            tag_list.append(t)
    fm["tags"] = tag_list
    fm.setdefault("manba", source)

    _write_note(target, fm, body)
    return target


def sync_lead_to_vault(
    lead_id: int | str,
    lead_name: str,
    phone: Optional[str] = None,
    price: int | float = 0,
    odam_name: Optional[str] = None,
    telegram: Optional[str] = None,
    note: Optional[str] = None,
    vault_path: Optional[Path] = None,
) -> Optional[Path]:
    """Create or update an amoCRM lead note in `70-AmoCRM/<name (id)>/<name (id)>.md`."""
    vault = vault_path or resolve_vault_path()
    if not vault:
        return None

    folder_name = f"{_sanitize_filename(lead_name, max_len=50)} ({lead_id})"
    lead_path = vault / "70-AmoCRM" / folder_name / f"{folder_name}.md"
    fm, body = _read_note(lead_path) if lead_path.exists() else (
        {"type": "amocrm-lead", "nom": lead_name, "lead_id": int(lead_id) if str(lead_id).isdigit() else lead_id},
        f"\n# {lead_name}\n",
    )

    if phone:
        fm["telefon"] = str(phone).strip()
    fm["narx"] = price
    fm["tags"] = list(dict.fromkeys((fm.get("tags") or []) + ["amocrm"]))

    person_path = sync_person_to_vault(
        name=odam_name or lead_name,
        phone=phone,
        telegram=telegram,
        source="amoCRM",
        vault_path=vault,
    )
    if person_path:
        fm["odam"] = f"[[70-Odamlar/{person_path.stem}]]"

    if note and note.strip() and note.strip() not in body:
        body = body.rstrip("\n") + f"\n- {note.strip()}\n"

    _write_note(lead_path, fm, body)

    if person_path:
        p_fm, p_body = _read_note(person_path)
        lead_rel = lead_path.relative_to(vault).with_suffix("").as_posix()
        link_line = f"- [[{lead_rel}|{lead_name}]]"
        if link_line not in p_body:
            if "## AmoCRM lidlar" in p_body:
                p_body = p_body.replace("## AmoCRM lidlar\n", f"## AmoCRM lidlar\n{link_line}\n", 1)
            else:
                p_body = p_body.rstrip("\n") + f"\n\n## AmoCRM lidlar\n{link_line}\n"
            _write_note(person_path, p_fm, p_body)

    return lead_path


def log_interaction_to_vault(
    person_name: str,
    actor: str,
    channel: str,
    summary: str,
    phone: Optional[str] = None,
    telegram: Optional[str] = None,
    timestamp: Optional[str] = None,
    vault_path: Optional[Path] = None,
) -> Optional[Path]:
    """Append a relationship/interaction entry to `## Munosabatlar tarixi` in `70-Odamlar/`."""
    if not summary or not summary.strip():
        return None
    person_path = sync_person_to_vault(
        name=person_name,
        phone=phone,
        telegram=telegram,
        source=channel,
        vault_path=vault_path,
    )
    if not person_path:
        return None

    ts = timestamp or datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"- `{ts}` | **{channel}** | {actor}: {summary.strip()}"
    fm, body = _read_note(person_path)
    if entry in body:
        return person_path

    header = "## Munosabatlar tarixi"
    if header in body:
        body = body.replace(f"{header}\n", f"{header}\n{entry}\n", 1)
    else:
        body = body.rstrip("\n") + f"\n\n{header}\n{entry}\n"

    _write_note(person_path, fm, body)
    return person_path


def sync_group_member_to_vault(
    chat_title: str,
    sender_name: str,
    phone: Optional[str] = None,
    telegram: Optional[str] = None,
    message_text: Optional[str] = None,
    vault_path: Optional[Path] = None,
) -> Optional[Path]:
    """Auto-import a Telegram group member (e.g. TEZ-NATIJA-7) into `70-Odamlar/`."""
    tag = re.sub(r"\s+", "-", chat_title.strip().upper())
    tag = re.sub(r"[^A-Z0-9_-]", "", tag)
    tags = [tag] if tag else []
    person_path = sync_person_to_vault(
        name=sender_name,
        phone=phone,
        telegram=telegram,
        tags=tags,
        source=f"Telegram ({chat_title})",
        vault_path=vault_path,
    )
    if person_path and message_text and len(message_text.strip()) > 10:
        log_interaction_to_vault(
            person_name=sender_name,
            actor=sender_name,
            channel=f"Telegram ({chat_title})",
            summary=message_text.strip()[:240],
            phone=phone,
            telegram=telegram,
            vault_path=vault_path,
        )
    return person_path

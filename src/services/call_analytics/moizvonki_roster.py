"""Moizvonki sotuvchilar ro'yxati uchun yagona manba.

Roster ``config/moizvonki_roster.json`` da saqlanadi va git bilan birga
deploy bo'ladi. ``MOIZVONKI_REP_NAMES`` env faqat fayl topilmasa ishlatiladi:
2026-10-29 da systemd ``Environment=`` dagi yangi rosterni ``EnvironmentFile``
(.env) ustidan yozib, hisobotda eski xodim (Farangiz) qaytib chiqqan edi.
Shu sabab fayl ustuvor, env esa faqat zaxira yo'l.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Dict, Iterable, Mapping

logger = logging.getLogger(__name__)

DEFAULT_ROSTER_PATH = Path(__file__).resolve().parents[3] / "config" / "moizvonki_roster.json"


def parse_rep_names(raw: str) -> Dict[str, str]:
    """``email:Ism,email2:Ism2`` formatini lug'atga aylantiradi."""
    names: Dict[str, str] = {}
    for part in (raw or "").split(","):
        if ":" in part:
            email, name = part.split(":", 1)
            email = email.strip().lower()
            name = name.strip()
            if email and name:
                names[email] = name
    return names


def roster_path(path: str | os.PathLike | None = None) -> Path:
    """Roster fayli yo'li: argument -> MOIZVONKI_ROSTER_FILE -> repo default."""
    if path:
        return Path(path)
    env_path = os.environ.get("MOIZVONKI_ROSTER_FILE", "").strip()
    if env_path:
        return Path(env_path)
    return DEFAULT_ROSTER_PATH


def _load_file(path: Path) -> Dict[str, str]:
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    reps = data.get("reps") if isinstance(data, dict) else None
    if not isinstance(reps, dict):
        raise ValueError(f"{path}: 'reps' obyekti topilmadi")
    return {
        str(account).strip().lower(): str(name).strip()
        for account, name in reps.items()
        if str(account).strip() and str(name).strip()
    }


def load_roster(path: str | os.PathLike | None = None) -> Dict[str, str]:
    """Sotuvchilar ro'yxatini qaytaradi (account -> ism)."""
    target = roster_path(path)
    env_names = parse_rep_names(os.environ.get("MOIZVONKI_REP_NAMES", ""))

    if target.is_file():
        try:
            file_names = _load_file(target)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            logger.error("[ROSTER] %s o'qilmadi: %s", target, exc)
            file_names = {}
        if file_names:
            if env_names and env_names != file_names:
                logger.warning(
                    "[ROSTER] MOIZVONKI_REP_NAMES env fayldan farq qiladi; "
                    "env e'tiborsiz qoldirildi (manba: %s)", target,
                )
            return file_names

    if env_names:
        logger.warning(
            "[ROSTER] %s topilmadi — MOIZVONKI_REP_NAMES env ishlatilmoqda",
            target,
        )
        return env_names

    logger.error("[ROSTER] Roster bo'sh: %s ham, MOIZVONKI_REP_NAMES ham yo'q", target)
    return {}


def load_excludes(path: str | os.PathLike | None = None) -> set[str]:
    """Hisobotdan chiqariladigan akkauntlar (admin hisobidan tashqari)."""
    target = roster_path(path)
    if not target.is_file():
        return set()
    try:
        with target.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("[ROSTER] %s o'qilmadi: %s", target, exc)
        return set()
    raw = data.get("exclude_accounts") if isinstance(data, dict) else None
    if not isinstance(raw, list):
        return set()
    return {str(item).strip().lower() for item in raw if str(item).strip()}


def unmapped_accounts(
    calls: Iterable[Mapping[str, object]],
    roster: Mapping[str, str],
    excludes: Iterable[str] = (),
) -> Dict[str, int]:
    """Rosterda yo'q, lekin qo'ng'iroq qilgan akkauntlar (jim yo'qotmaslik uchun)."""
    skip = {str(a).strip().lower() for a in excludes if str(a).strip()}
    known = {str(a).strip().lower() for a in roster}
    counts: Dict[str, int] = {}
    for call in calls:
        account = str(call.get("user_account") or "").strip().lower()
        if not account or account in known or account in skip:
            continue
        counts[account] = counts.get(account, 0) + 1
    return counts

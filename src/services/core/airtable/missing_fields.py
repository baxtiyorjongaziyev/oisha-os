"""Airtable "Loyihalar" jadvalida boʼsh qolgan muhim maydonlarni topib, masʼul PM boʼyicha guruhlaydi.

Natija jamoa guruhiga yuboriladi: har bir PM ismi bilan belgilanadi va oʼz loyihalaridagi
yetishmayotgan maydonlar roʼyxatini oladi. PM tayinlanmagan loyihalar alohida blokda chiqadi.
Sof funksiyalar (``collect_gaps``, ``format_message``) test uchun HTTPʼdan ajratilgan.
"""
from __future__ import annotations

import html
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Iterable, Optional

logger = logging.getLogger(__name__)

PROJECTS_TABLE_ID = "tblJbUobSlygSwYAI"
TEAM_TABLE_ID = "tbloj9riNIrGT1cZI"

# PM javob beradigan, qoʼlda kiritiladigan maydonlar.
REQUIRED_FIELDS: tuple[str, ...] = (
    "Sotuvchi",
    "Dizayner soatlari",
    "PM va Muloqot soatlari",
    "Pravkalar soni",
)

# Tugaganiga shuncha kundan koʼp boʼlgan loyihalar soʼralmaydi (eski arxivni bezovta qilmaslik).
FINISHED_GRACE_DAYS = 30
MAX_PER_PM = 10
NO_PM_KEY = ""


@dataclass
class ProjectGap:
    record_id: str
    name: str
    missing: list[str]


@dataclass
class GapReport:
    by_pm: dict[str, list[ProjectGap]] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return sum(len(v) for v in self.by_pm.values())


def _is_empty(value) -> bool:
    return value in (None, "", [], {}) or value is False


def _parse_date(value) -> Optional[date]:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value[:10]).date()
    except ValueError:
        return None


def collect_gaps(
    projects: Iterable[dict],
    team_names: dict[str, str],
    today: date,
    required: tuple[str, ...] = REQUIRED_FIELDS,
) -> GapReport:
    """Yozuvlardan PM ismi boʼyicha guruhlangan boʼshliqlar hisobotini quradi."""
    report = GapReport()
    cutoff = today - timedelta(days=FINISHED_GRACE_DAYS)
    for rec in projects:
        fields = rec.get("fields") or {}
        end = _parse_date(fields.get("END sana"))
        if end and end < cutoff:
            continue
        missing = [name for name in required if _is_empty(fields.get(name))]
        if not missing:
            continue
        pm_ids = fields.get("PM") or []
        pm_name = team_names.get(pm_ids[0], NO_PM_KEY) if pm_ids else NO_PM_KEY
        project_name = str(fields.get("Loyiha nomi") or fields.get("Mijoz nomi") or rec.get("id"))
        report.by_pm.setdefault(pm_name, []).append(
            ProjectGap(record_id=rec["id"], name=project_name, missing=missing)
        )
    return report


def _record_url(base_id: str, record_id: str) -> str:
    return f"https://airtable.com/{base_id}/{PROJECTS_TABLE_ID}/{record_id}"


def _format_block(title: str, gaps: list[ProjectGap], base_id: str) -> list[str]:
    lines = [title]
    for gap in gaps[:MAX_PER_PM]:
        link = f"<a href=\"{_record_url(base_id, gap.record_id)}\">{html.escape(gap.name)}</a>"
        lines.append(f"• {link} — {html.escape(', '.join(gap.missing))}")
    if len(gaps) > MAX_PER_PM:
        lines.append(f"… yana {len(gaps) - MAX_PER_PM} ta loyiha")
    return lines


def format_message(report: GapReport, base_id: str) -> Optional[str]:
    """Guruhga yuboriladigan HTML matn. Boʼshliq boʼlmasa ``None``."""
    if report.total == 0:
        return None
    lines = [
        "<b>📋 Airtable: yetishmayotgan maʼlumotlar</b>",
        "Har bir masʼul oʻz loyihasini tekshirib, boʻsh maydonlarni toʻldirsin.",
        "",
    ]
    named = sorted((k for k in report.by_pm if k != NO_PM_KEY), key=str.lower)
    for pm in named:
        title = f"<b>{html.escape(pm)}</b> ({len(report.by_pm[pm])} ta loyiha):"
        lines.extend(_format_block(title, report.by_pm[pm], base_id))
        lines.append("")
    if NO_PM_KEY in report.by_pm:
        title = f"<b>⚠️ PM tayinlanmagan</b> ({len(report.by_pm[NO_PM_KEY])} ta) — rahbar PM belgilasin:"
        lines.extend(_format_block(title, report.by_pm[NO_PM_KEY], base_id))
    return "\n".join(lines).strip()


def _fetch_all(client, table_id: str, fields: Optional[list[str]] = None) -> list[dict]:
    url = client._table_url(table_id)
    params: dict = {"pageSize": 100}
    if fields:
        params["fields[]"] = fields
    records: list[dict] = []
    while True:
        response = client._request("GET", url, params=params)
        if response.status_code != 200:
            logger.error("[AT-GAPS] %s fetch failed: HTTP %s", table_id, response.status_code)
            return []
        payload = response.json()
        records.extend(payload.get("records") or [])
        offset = payload.get("offset")
        if not offset:
            return records
        params["offset"] = offset


def build_report_message(today: date, client=None) -> Optional[str]:
    """Airtableʼdan oʼqib, tayyor xabar matnini qaytaradi (sinxron, to_thread uchun)."""
    if client is None:
        from src.services.core.airtable.sync import AirtableSync

        client = AirtableSync()
    team = _fetch_all(client, TEAM_TABLE_ID, ["Ism"])
    team_names = {r["id"]: str((r.get("fields") or {}).get("Ism") or "") for r in team}
    projects = _fetch_all(
        client,
        PROJECTS_TABLE_ID,
        ["Loyiha nomi", "Mijoz nomi", "PM", "END sana", *REQUIRED_FIELDS],
    )
    if not projects:
        return None
    report = collect_gaps(projects, team_names, today)
    return format_message(report, client.base_id)

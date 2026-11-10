"""
AmoCRM Hygiene & Capacity Engine.
Intizom nazorati ("Vazifasiz bitim — oʻlik bitim!") va
500 ta bitimlik limitga yaqinlashganda ogohlantirish beruvchi xavfsiz servis.
DIQQAT: Turgʻun bitimlarni avtomatik Lost (143) ga yopish TAQIQLANADI.
Faqat nomzodlar aniqlanadi va owner/ROP koʻrib chiqishi uchun hisobot beriladi.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import requests

from src.services.core.crm.amocrm_pipeline_config import (
    SALES_PIPELINE_ID,
    STATUS_LOST,
)
from src.services.core.crm.amocrm_sync import AmoCRMSync
from src.services.core.leads.lead_filter_guard import is_excluded_contact
from src.settings import settings

logger = logging.getLogger("AmoCRMHygiene")

DEFAULT_SAFE_CAPACITY_LIMIT = 480
DEFAULT_AMOCRM_HARD_LIMIT = 500
RESPONSIBLE_SOTUV_USER_ID = 13021974
TASK_TEXT_DEFAULT = "Oisha-OS: Mijoz bilan aloqaga chiqish va keyingi aniq qadamni belgilash"


class AmoCRMHygieneService:
    """AmoCRM intizomi va sigʻimini nazorat qiluvchi xavfsiz servis."""

    def __init__(
        self,
        amocrm: Optional[AmoCRMSync] = None,
        bot_runtime: Any = None,
        reports_dir: Optional[Path] = None,
    ) -> None:
        self.amocrm = amocrm or AmoCRMSync()
        self.bot_runtime = bot_runtime
        self.reports_dir = reports_dir or (
            Path(__file__).resolve().parents[4] / "data" / "reports"
        )
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    async def run_hygiene_cycle(
        self,
        dry_run: bool = False,
        auto_archive: bool = False,
        capacity_threshold: int = DEFAULT_SAFE_CAPACITY_LIMIT,
        max_stagnant_days: int = 30,
    ) -> Dict[str, Any]:
        """Xavfsiz gigiyena sikli: vazifalarni taʼminlash va sigʻim boʻyicha hisobot berish."""
        logger.info("[HYGIENE] Gigiyena sikli boshlandi (dry_run=%s, auto_archive=%s)", dry_run, auto_archive)
        active_leads = await self.fetch_all_active_leads()
        active_count = len(active_leads)
        logger.info("[HYGIENE] Jami aktiv bitimlar: %s / %s", active_count, DEFAULT_AMOCRM_HARD_LIMIT)

        open_task_ids = await self.fetch_open_task_lead_ids()
        tasks_created = await self.enforce_tasks_on_active_deals(
            active_leads=active_leads,
            open_task_ids=open_task_ids,
            dry_run=dry_run,
        )

        stagnant_candidates: List[Dict[str, Any]] = []
        backup_file: Optional[str] = None
        archived_count = 0

        if active_count >= capacity_threshold:
            logger.warning(
                "[HYGIENE] Aktiv bitimlar (%s) xavfli ostonadan (%s) oshdi. Turgʻun nomzodlar qidirilmoqda...",
                active_count,
                capacity_threshold,
            )
            stagnant_candidates, backup_file, archived_count = await self.inspect_and_handle_capacity(
                active_leads=active_leads,
                max_stagnant_days=max_stagnant_days,
                auto_archive=auto_archive and not dry_run,
            )

        report = {
            "timestamp": int(time.time()),
            "dry_run": dry_run,
            "auto_archive_enabled": auto_archive,
            "total_active_before": active_count,
            "total_active_after": active_count - archived_count,
            "hard_limit": DEFAULT_AMOCRM_HARD_LIMIT,
            "free_slots": DEFAULT_AMOCRM_HARD_LIMIT - (active_count - archived_count),
            "tasks_created": tasks_created,
            "stagnant_candidates_count": len(stagnant_candidates),
            "archived_leads": archived_count,
            "backup_file": backup_file,
            "status": "safe" if (active_count - archived_count) < capacity_threshold else "warning",
        }

        if not dry_run and (tasks_created > 0 or len(stagnant_candidates) > 0 or active_count >= capacity_threshold):
            await self.send_hygiene_digest(report)

        return report

    async def fetch_all_active_leads(self) -> List[Dict[str, Any]]:
        """AmoCRMʼdagi barcha ochiq bitimlarni sahifalab olish."""
        self.amocrm._load_token()
        headers = self.amocrm._get_headers()
        base_url = self.amocrm.base_url

        def _fetch() -> List[Dict[str, Any]]:
            page = 1
            active: List[Dict[str, Any]] = []
            while True:
                url = f"{base_url}/api/v4/leads?limit=250&page={page}&with=contacts"
                resp = requests.get(url, headers=headers, timeout=25)
                if resp.status_code != 200:
                    break
                data = resp.json()
                batch = data.get("_embedded", {}).get("leads", []) or []
                if not batch:
                    break
                for ld in batch:
                    if ld.get("status_id") not in (142, 143):
                        active.append(ld)
                page += 1
                if len(batch) < 250:
                    break
            return active

        try:
            return await asyncio.to_thread(_fetch)
        except Exception as exc:
            logger.error("[HYGIENE] Aktiv bitimlarni yuklashda xato: %s", exc)
            return []

    async def fetch_open_task_lead_ids(self) -> Set[int]:
        """Aktiv vazifasi mavjud bitimlar identifikatorlarini toʻplash."""
        self.amocrm._load_token()
        headers = self.amocrm._get_headers()
        base_url = self.amocrm.base_url

        def _fetch() -> Set[int]:
            page = 1
            lead_ids: Set[int] = set()
            while True:
                url = f"{base_url}/api/v4/tasks?limit=250&page={page}&filter[is_completed]=0"
                resp = requests.get(url, headers=headers, timeout=25)
                if resp.status_code != 200:
                    break
                data = resp.json()
                batch = data.get("_embedded", {}).get("tasks", []) or []
                if not batch:
                    break
                for t in batch:
                    if t.get("entity_type") in ("leads", 2):
                        lead_ids.add(int(t.get("entity_id")))
                page += 1
                if len(batch) < 250:
                    break
            return lead_ids

        try:
            return await asyncio.to_thread(_fetch)
        except Exception as exc:
            logger.error("[HYGIENE] Vazifalarni yuklashda xato: %s", exc)
            return set()

    async def enforce_tasks_on_active_deals(
        self,
        active_leads: List[Dict[str, Any]],
        open_task_ids: Set[int],
        dry_run: bool = False,
    ) -> int:
        """Vazifasiz qolgan aktiv bitimlarga 24 soatlik vazifa biriktirish."""
        needing_task = [ld for ld in active_leads if int(ld.get("id")) not in open_task_ids]
        if not needing_task:
            logger.info("[HYGIENE] Barcha aktiv bitimlarda ochiq vazifalar mavjud.")
            return 0

        logger.info("[HYGIENE] %s ta bitimda vazifa yoʻq. Vazifalar yaratilmoqda...", len(needing_task))
        if dry_run:
            return len(needing_task)

        deadline = int(time.time()) + (24 * 3600)
        headers = self.amocrm._get_headers()
        base_url = self.amocrm.base_url
        created_count = 0
        batch_size = 50

        for i in range(0, len(needing_task), batch_size):
            batch = needing_task[i : i + batch_size]
            payload = [
                {
                    "entity_id": int(ld.get("id")),
                    "entity_type": "leads",
                    "text": TASK_TEXT_DEFAULT,
                    "complete_till": deadline,
                    "responsible_user_id": ld.get("responsible_user_id") or RESPONSIBLE_SOTUV_USER_ID,
                }
                for ld in batch
            ]
            try:
                resp = await asyncio.to_thread(
                    requests.post,
                    f"{base_url}/api/v4/tasks",
                    headers=headers,
                    json=payload,
                    timeout=25,
                )
                if resp.status_code in (200, 201):
                    created_count += len(batch)
                await asyncio.sleep(0.2)
            except Exception as exc:
                logger.error("[HYGIENE] Vazifa yaratish partiyasida xato: %s", exc)

        return created_count

    async def inspect_and_handle_capacity(
        self,
        active_leads: List[Dict[str, Any]],
        max_stagnant_days: int = 30,
        auto_archive: bool = False,
    ) -> tuple[List[Dict[str, Any]], Optional[str], int]:
        """Turgʻun bitimlarni aniqlash. Avtomatik yopilmaydi — faqat hisobot beriladi."""
        now_ts = int(time.time())
        candidates: List[Dict[str, Any]] = []

        for ld in active_leads:
            lead_name = ld.get("name") or ""
            excluded, _ = is_excluded_contact(name=lead_name)
            if excluded:
                continue

            created_at = int(ld.get("created_at") or now_ts)
            age_days = (now_ts - created_at) / 86400
            contacts = ld.get("_embedded", {}).get("contacts", []) or []

            # 1. Kontaktsiz va 14 kundan oshgan
            if len(contacts) == 0 and age_days > 14:
                candidates.append(ld)
                continue

            # 2. Qayta aloqa bosqichida 20 kundan oshgan
            if ld.get("pipeline_id") == SALES_PIPELINE_ID and ld.get("status_id") == 87609518 and age_days > 20:
                candidates.append(ld)
                continue

            # 3. 30 kundan oshgan turgʻun bitimlar
            if age_days > max_stagnant_days and ld.get("status_id") not in (88871066, 89380154):
                candidates.append(ld)

        if not candidates:
            return [], None, 0

        backup_file = self.reports_dir / f"amocrm_backup_{now_ts}.json"
        try:
            with open(backup_file, "w", encoding="utf-8") as f:
                json.dump(active_leads, f, ensure_ascii=False, indent=2)
            logger.info("[HYGIENE] Zaxira nusxa saqlandi: %s", backup_file)
        except Exception as exc:
            logger.warning("[HYGIENE] Zaxira nusxa saqlashda xato: %s", exc)

        # Xavfsizlik qoidasi: auto_archive False boʻlsa, hech qanday bitim oʻzgartirilmaydi!
        if not auto_archive:
            logger.warning(
                "[HYGIENE] %s ta turgʻun bitim nomzodi aniqlandi (avtomatik arxivlash oʻchirilgan — koʻrib chiqish kerak).",
                len(candidates),
            )
            return candidates, str(backup_file), 0

        # Faqat egasi/admini qatʼiy ruxsat bergandagina arxivlash
        headers = self.amocrm._get_headers()
        base_url = self.amocrm.base_url
        archived_count = 0
        batch_size = 50

        for i in range(0, len(candidates), batch_size):
            batch = candidates[i : i + batch_size]
            payload = [{"id": int(ld.get("id")), "status_id": STATUS_LOST} for ld in batch]
            try:
                resp = await asyncio.to_thread(
                    requests.patch,
                    f"{base_url}/api/v4/leads",
                    headers=headers,
                    json=payload,
                    timeout=25,
                )
                if resp.status_code in (200, 201):
                    archived_count += len(batch)
                await asyncio.sleep(0.2)
            except Exception as exc:
                logger.error("[HYGIENE] Arxivlash partiyasida xato: %s", exc)

        return candidates, str(backup_file), archived_count

    async def send_hygiene_digest(self, report: Dict[str, Any]) -> None:
        """Telegram orqali intizom va sigʻim hisobotini yuborish."""
        if not self.bot_runtime:
            return
        group_id = getattr(settings, "CRM_GROUP_ID", None) or getattr(settings, "TEAM_GROUP_ID", None)
        if not group_id:
            return

        icon = "✅" if report.get("status") == "safe" else "⚠️"
        total = report.get("total_active_after", 0)
        free = report.get("free_slots", 0)
        tasks = report.get("tasks_created", 0)
        candidates_count = report.get("stagnant_candidates_count", 0)

        warning_note = ""
        if candidates_count > 0:
            warning_note = (
                f"\n⚠️ <b>Diqqat:</b> {candidates_count} ta turgʻun bitim aniqlandi.\n"
                f"<i>(Avtomatik yopilmadi — ROP/sotuvchi koʻrib chiqishi shart).</i>\n"
            )

        msg = (
            f"🧹 <b>AmoCRM Gigiyena va Intizom Hisoboti</b>\n\n"
            f"• {icon} <b>Aktiv bitimlar:</b> {total} / {DEFAULT_AMOCRM_HARD_LIMIT}\n"
            f"• 🆓 <b>Boʻsh joy:</b> {free} ta bitim\n"
            f"• 📝 <b>Yangi biriktirilgan vazifalar:</b> +{tasks} ta\n"
            f"{warning_note}\n"
            f"<i>\"Vazifasiz bitim — oʻlik bitim!\" qoidasi nazoratda.</i>"
        )
        try:
            await self.bot_runtime.send_message(
                chat_id=group_id,
                text=msg,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        except Exception as exc:
            logger.warning("[HYGIENE] Telegram xabarnoma xatosi: %s", exc)

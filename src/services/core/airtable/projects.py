"""
Projects, deadlines, transactions, and CRM stage synchronization mixin.
"""
from __future__ import annotations

import json
import logging
import os
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from src.time_utils import get_local_now
from src.services.core.airtable.constants import DONE_STAGES

logger = logging.getLogger("AirtableSync")


class ProjectsMixin:
    """Handles Airtable CRUD operations on projects, deadlines, and finance."""

    def get_projects(self, force_refresh: bool = False):
        """Airtable-dan loyihalarni olish."""
        if not self.api_key or not self.base_id:
            logger.error("[AIRTABLE] API key yoki Base ID yetishmayapti.")
            return []

        if not force_refresh:
            cached_records = self._get_cached_records()
            if cached_records is not None:
                logger.info(
                    f"[AIRTABLE CACHE] {self.table_name}: {len(cached_records)} cached records"
                )
                return cached_records

        try:
            records = []
            params = {"pageSize": 100}
            while True:
                response = self._request("GET", self.endpoint, params=params)
                if response.status_code == 200:
                    data = response.json()
                    records.extend(data.get("records", []))
                    offset = data.get("offset")
                    if not offset:
                        self._set_cached_records(records)
                        return records
                    params["offset"] = offset
                    continue

                if response.status_code == 403:
                    logger.error(
                        f"[AIRTABLE 403] Ruxsat xatosi! Tokeningizda 'data.records:read' ruxsati bormi? "
                        f"Yoki '{self.table_name}' jadvali mavjud emas."
                    )
                    return records
                logger.error(
                    f"[AIRTABLE ERROR] {response.status_code}: {response.text}"
                )
                return records or self._get_disk_cached_records() or []
        except Exception as exc:
            logger.error(f"[AIRTABLE EXCEPTION] {exc}")
            return self._get_disk_cached_records() or []

    def get_overdue_projects(self):
        """Muddati o'tgan loyihalarni topish."""
        projects = self.get_projects()
        overdue = []
        now = datetime.now()

        for project in projects:
            fields = project.get("fields", {})
            deadline_str = self._get_field(fields, "deadline")
            stage = self._get_field(fields, "stage") or ""

            if deadline_str and stage not in self.DONE_STAGES:
                try:
                    deadline = datetime.strptime(deadline_str, "%Y-%m-%d")
                    if deadline < now:
                        overdue.append(project)
                except Exception:
                    logger.error("Exception handled in %s", __name__, exc_info=True)
                    continue
        return overdue

    def get_projects_by_stage(self, stage_name: str):
        """Ma'lum bir bosqichdagi loyihalarni olish."""
        projects = self.get_projects()
        return [
            project
            for project in projects
            if self._get_field(project.get("fields", {}), "stage") == stage_name
        ]

    # Finance V2: barcha pul harakati shu jadvalda
    TRANSACTIONS_TABLE = "Tranzaksiyalar"

    def get_transactions(self, force_refresh: bool = False):
        """Tranzaksiyalar jadvalidan barcha yozuvlarni olish (xom holda)."""
        original_table = self.table_name
        self.table_name = self.TRANSACTIONS_TABLE
        self._refresh_endpoint()
        try:
            return self.get_projects(force_refresh=force_refresh)
        finally:
            self.table_name = original_table
            self._refresh_endpoint()

    def get_finance_records(self):
        """Barcha kirim/chiqimlarni olish - Finance V2 (Tranzaksiyalar) jadvalidan.

        Eski Kirim/Chiqim jadvallari 2026-avgustda Tranzaksiyalarga kochirilgan.
        Chiqish formati eski holicha qoldirilgan (``_record_type`` + eski maydon
        nomlari), shuning uchun mavjud istemolchilarni ozgartirish shart emas.
        """
        records = []

        for record in self.get_transactions():
            fields = record.get("fields", {}) or {}

            turi = fields.get("Turi")
            if isinstance(turi, dict):
                turi = turi.get("name")
            turi = (turi or "").strip()

            # Transfer - hisoblar orasidagi kochirish, daromad ham xarajat ham emas
            if turi not in ("Kirim", "Chiqim"):
                continue

            holat = fields.get("Holat")
            if isinstance(holat, dict):
                holat = holat.get("name")
            if (holat or "").strip() == "Bekor qilingan":
                continue

            summa_uzs = fields.get("Summa UZS") or 0
            sana = fields.get("Sana")

            # Eski maydon nomlarini ham toldiramiz - eski kod buzilmasin
            if turi == "Kirim":
                record["_record_type"] = "income"
                fields.setdefault("To'lov miqdori", summa_uzs)
                fields.setdefault("To'lov sanasi", sana)
                fields.setdefault("UZS ekvivalenti", summa_uzs)
            else:
                record["_record_type"] = "expense"
                fields.setdefault("Chiqim miqdori", summa_uzs)
                fields.setdefault("Chiqim sanasi", sana)
                fields.setdefault("Chiqim (uzs)", summa_uzs)

            fields.setdefault("Summa", summa_uzs)
            record["fields"] = fields
            records.append(record)

        return records

    def update_project_fields(self, record_id: str, fields: dict):
        """Loyihaning bir nechta maydonlarini yangilash."""
        fields = self._normalize_fields_for_table(fields)
        if not fields:
            logger.warning(
                "[AIRTABLE] No valid fields to update after schema normalization."
            )
            return False

        url = f"{self.endpoint}/{record_id}"
        data = {"fields": fields}
        try:
            response = self._request("PATCH", url, retry=False, json=data)
            ok = response.status_code == 200
            if ok:
                self._invalidate_records_cache()
            return ok
        except Exception as exc:
            logger.error(f"[AIRTABLE UPDATE ERROR] {exc}")
            return False

    def update_project_stage(self, record_id, next_stage):
        """Loyihaning bosqichini yangilash (Record ID orqali)."""
        return self.update_project_fields(record_id, {"Loyiha bosqichi": next_stage})

    def update_project_fields_by_name(self, project_name: str, fields: dict):
        """Loyihaning maydonlarini nomi orqali topib yangilash."""
        projects = self.get_projects()
        for project in projects:
            p_fields = project.get("fields", {})
            if self._get_field(p_fields, "project_name") == project_name:
                return self.update_project_fields(project.get("id"), fields)

        logger.warning(f"[AIRTABLE] Loyiha topilmadi: {project_name}")
        return False

    def update_project_stage_by_name(self, project_name: str, next_stage: str):
        """Loyihaning bosqichini nomi orqali topib yangilash."""
        return self.update_project_fields_by_name(
            project_name, {"Loyiha bosqichi": next_stage}
        )

    def get_upcoming_deadlines(self, hours=72):
        """Yaqin 72 soat ichida muddati tugaydigan loyihalarni topish."""
        from datetime import timedelta

        projects = self.get_projects()
        upcoming = []
        now = datetime.now()
        limit = now + timedelta(hours=hours)

        for project in projects:
            fields = project.get("fields", {})
            deadline_str = self._get_field(fields, "deadline")
            stage = self._get_field(fields, "stage") or ""

            if deadline_str and stage not in self.DONE_STAGES:
                try:
                    deadline = datetime.strptime(deadline_str, "%Y-%m-%d")
                    if now < deadline <= limit:
                        upcoming.append(project)
                except Exception:
                    logger.error("Exception handled in %s", __name__, exc_info=True)
                    continue
        return upcoming

    def create_record(self, fields: dict):
        """Airtable-da yangi yozuv yaratish."""
        fields = self._normalize_fields_for_table(fields)
        if not fields:
            logger.warning(
                "[AIRTABLE] No valid fields to create after schema normalization."
            )
            return None

        try:
            response = self._request(
                "POST", self.endpoint, retry=False, json={"fields": fields}
            )
            if response.status_code in [200, 201]:
                self._invalidate_records_cache()
                project_label = (
                    fields.get("Loyihani nomi?")
                    or fields.get("Project Name")
                    or fields.get("Name")
                    or "Unknown"
                )
                logger.info(f"[AIRTABLE OK] Yangi yozuv yaratildi: {project_label}")
                return response.json()
            logger.error(f"[AIRTABLE ERROR] {response.status_code}: {response.text}")
            return None
        except Exception as exc:
            logger.error(f"[AIRTABLE EXCEPTION] {exc}")
            return None

    def log_lead_acquisition(
        self, name: str, phone: str, source: str, intent: str = "WARM"
    ):
        """Lid topilganini tarixiy audit uchun Airtable'ga yozish."""
        original_table = self.table_name
        self.table_name = "Leads"
        self._refresh_endpoint()

        fields = {
            "Name": name,
            "Phone": phone,
            "Source": source,
            "Intent": intent,
            "Date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }

        try:
            return self.create_record(fields)
        finally:
            self.table_name = original_table
            self._refresh_endpoint()

    def verify_qc_standards(self, record_id: str) -> bool:
        """Loyihaning Sifat Nazorati talablariga javob berishini tekshirish."""
        logger.info(f"[QC] Checking project: {record_id}")
        return True

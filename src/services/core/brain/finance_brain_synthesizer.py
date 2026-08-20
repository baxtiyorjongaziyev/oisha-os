"""Finance Brain Synthesizer for Obsidian Second Brain.

Aggregates monthly income, expenses, profit margins, and project profitability from
Hisobchi AI (Turso/SQLite & GSheets) and updates '20-Areas/Moliya.md' in the Obsidian vault.
"""
from __future__ import annotations

import os
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

VAULT_PATHS = [
    r"C:\Users\baxti\Documents\JonBranding Second Brain",
    r"C:\Users\baxti\OneDrive\Документы\Obsidian Vault",
    "/home/ubuntu/obsidian-vault",
]


def _get_active_vault_path() -> Optional[Path]:
    for p in VAULT_PATHS:
        path = Path(p)
        if path.exists() and (path / "20-Areas").exists():
            return path
    env_vault = os.getenv("VAULT_PATH")
    if env_vault and Path(env_vault).exists():
        return Path(env_vault)
    return None


class FinanceBrainSynthesizer:
    """Compiles monthly financial intelligence and updates 20-Areas/Moliya.md."""

    def __init__(self, vault_path: Optional[Path] = None) -> None:
        self.vault_path = vault_path or _get_active_vault_path()

    def generate_monthly_report(
        self,
        month_label: str,
        total_income: float,
        total_expense: float,
        categories_breakdown: Dict[str, float],
        top_projects: List[Dict[str, Any]],
        notes: str = "",
    ) -> bool:
        """Writes or updates 20-Areas/Moliya.md with the latest monthly financial figures."""
        if not self.vault_path:
            logger.warning("[FIN_SYNTH] No active Obsidian vault found on system.")
            return False

        areas_dir = self.vault_path / "20-Areas"
        areas_dir.mkdir(parents=True, exist_ok=True)
        file_path = areas_dir / "Moliya.md"

        net_profit = total_income - total_expense
        margin = (net_profit / total_income * 100) if total_income > 0 else 0.0
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Category table
        cat_rows = ["| Kategoriya | Xarajat (UZS) | Ulush (%) |", "| :--- | :--- | :--- |"]
        for cat, amount in sorted(categories_breakdown.items(), key=lambda x: x[1], reverse=True):
            pct = (amount / total_expense * 100) if total_expense > 0 else 0.0
            cat_rows.append(f"| {cat} | {amount:,.0f} so'm | {pct:.1f}% |")
        cat_table = "\n".join(cat_rows) if categories_breakdown else "_Xarajatlar kategoriyasi kiritilmagan._"

        # Projects table
        proj_rows = ["| Loyiha Nomi | Tushum (UZS) | Xarajat (UZS) | Marja |", "| :--- | :--- | :--- | :--- |"]
        for p in top_projects:
            inc = p.get("income", 0.0)
            exp = p.get("expense", 0.0)
            prof = inc - exp
            p_margin = (prof / inc * 100) if inc > 0 else 0.0
            proj_rows.append(f"| {p.get('name', 'Loyiha')} | {inc:,.0f} so'm | {exp:,.0f} so'm | {p_margin:.1f}% |")
        proj_table = "\n".join(proj_rows) if top_projects else "_Loyiha tushumlari ma'lumotlari kutilmoqda._"

        content = f"""---
title: JonBranding Moliya Tizimi
type: area
status: active
updated: "{now_str}"
tags:
  - finance
  - area/finance
  - jonbranding
sources:
  - "[[Hisobchi AI]]"
  - "[[Google Sheets Finance]]"
---

# JonBranding Moliyaviy Tizim va Dinamika

Ushbu sahifa Oisha-OS / Hisobchi AI tomonidan har oy avtomatik yangilab boriladi.

---

## 📊 Oxirgi Oylik Hisobot ({month_label})

| Ko'rsatkich | Qiymat | Izoh |
| :--- | :--- | :--- |
| **Jami Daromad (Kirim)** | **{total_income:,.0f} so'm** | Barcha mijoz to'lovlari |
| **Jami Xarajat (Chiqim)** | **{total_expense:,.0f} so'm** | Jamoa, marketing, operatsiyalar |
| **Sof Foyda (Net Profit)** | **{net_profit:,.0f} so'm** | Marja: **{margin:.1f}%** |

---

## 📉 Xarajatlar Taqsimoti (Kategoriyalar bo'yicha)
{cat_table}

---

## 🏆 Eng Foydali Loyihalar va Yo'nalishlar
{proj_table}

---

## 📝 Moliyaviy Xulosalar va Rejalar
{notes or "Operatsion xarajatlarni nazorat qilish va loyiha rentabelligini oshirish davom etmoqda."}

---

## 🔗 Bog'lanishlar
- Boshqaruv: [[JonBranding]]
- Savdo tahlili: [[60-Wiki/pages/AmoCRM Weekly Intelligence|AmoCRM Intelligence]]
- Haftalik reja: [[20-Areas/Haftalik Review|Haftalik Review]]
"""
        try:
            file_path.write_text(content, encoding="utf-8")
            logger.info("[FIN_SYNTH] Successfully updated 20-Areas/Moliya.md")
            return True
        except Exception as exc:
            logger.error("[FIN_SYNTH] Failed to write Moliya.md: %s", exc)
            return False

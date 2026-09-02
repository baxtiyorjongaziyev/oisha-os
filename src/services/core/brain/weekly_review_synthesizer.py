"""Weekly Review Synthesizer for Obsidian Second Brain.

Automates the weekly business reflection rhythm answering:
1. What was completed & delivered this week?
2. Where did we get stuck (bottlenecks)?
3. What are the TOP-3 North Star goals for next week?
Updates '20-Areas/Haftalik Review.md' and daily notes in '50-Daily/'.
"""
from __future__ import annotations

import os
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

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


class WeeklyReviewSynthesizer:
    """Generates automated weekly review synthesis notes in Obsidian."""

    def __init__(self, vault_path: Optional[Path] = None) -> None:
        self.vault_path = vault_path or _get_active_vault_path()

    def generate_weekly_review(
        self,
        week_label: str,
        completed_items: List[str],
        bottlenecks: List[str],
        top_goals_next_week: List[str],
        revenue_summary: str = "",
        team_learnings: str = "",
    ) -> bool:
        """Writes or updates 20-Areas/Haftalik Review.md and 50-Daily/."""
        if not self.vault_path:
            logger.warning("[WEEKLY_SYNTH] No active Obsidian vault found on system.")
            return False

        areas_dir = self.vault_path / "20-Areas"
        areas_dir.mkdir(parents=True, exist_ok=True)
        file_path = areas_dir / "Haftalik Review.md"

        now_dt = datetime.now(timezone.utc)
        now_str = now_dt.strftime("%Y-%m-%d")

        done_list = "\n".join([f"- [x] {item}" for item in completed_items]) if completed_items else "- _Topshirilgan loyihalar qayd etilmoqda._"
        stuck_list = "\n".join([f"- ⚠️ {item}" for item in bottlenecks]) if bottlenecks else "- _Jiddiy bloklovchi muammolar kuzatilmadi._"
        goals_list = "\n".join([f"- [ ] 🎯 **{item}**" for item in top_goals_next_week]) if top_goals_next_week else "- [ ] 🎯 Asosiy sotuvlar va yetkazish maqsadlari"

        content = f"""---
title: Haftalik Review va Boshqaruv Ritmi
type: area
status: active
updated: "{now_str}"
tags:
  - weekly-review
  - management
  - jonbranding
sources:
  - "[[JonBranding Operations]]"
  - "[[AmoCRM Live Sync]]"
---

# Haftalik Review va Tahlil ({week_label})

Har haftalik 10 daqiqalik boshqaruv tahlili: erishilgan yutuqlar, to'xtab qolgan nuqtalar va keyingi haftaning bosh yo'nalishlari.

---

## 1. ✅ Bu hafta nimalar yakunlandi va topshirildi?
{done_list}

{f"**Haftalik Moliya/Daromad:** {revenue_summary}" if revenue_summary else ""}

---

## 2. 🛑 Qayerda to'xtab qoldik (Bottlenecks / To'siqlar)?
{stuck_list}

---

## 3. 🚀 Keyingi haftaning TOP-3 Asosiy Maqsadi (North Stars):
{goals_list}

---

## 💡 O'rganilgan Saboqlar va Jamoa Tizimi (SOP)
{team_learnings or "_Jamoa konveyeri va mijozlar bilan muloqot intizomi mustahkamlanmoqda._"}

---

## 🔗 Bog'lanishlar
- Markaz: [[JonBranding]]
- Boshqaruv: [[20-Areas/JonBranding Operations|Operatsiyalar]]
- Moliya: [[20-Areas/Moliya|Moliya Tizimi]]
- Sotuvlar: [[60-Wiki/pages/AmoCRM Weekly Intelligence|AmoCRM Intelligence]]
"""
        try:
            file_path.write_text(content, encoding="utf-8")
            logger.info("[WEEKLY_SYNTH] Successfully updated 20-Areas/Haftalik Review.md")

            # Also ensure a daily note entry exists in 50-Daily/
            daily_dir = self.vault_path / "50-Daily"
            daily_dir.mkdir(parents=True, exist_ok=True)
            daily_file = daily_dir / f"{now_str}.md"
            daily_entry = f"\n\n## 📅 Haftalik Review ({week_label})\n- [[20-Areas/Haftalik Review|Haftalik tahlil notasiga o'tish]]\n"
            if daily_file.exists():
                existing = daily_file.read_text(encoding="utf-8")
                if "Haftalik Review" not in existing:
                    daily_file.write_text(existing + daily_entry, encoding="utf-8")
            else:
                daily_file.write_text(f"# {now_str}\n{daily_entry}", encoding="utf-8")

            return True
        except Exception as exc:
            logger.error("[WEEKLY_SYNTH] Failed to write Haftalik Review note: %s", exc)
            return False

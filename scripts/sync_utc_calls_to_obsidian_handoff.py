"""
Sync UTC Analyzed Client Conversations & Agreements to Obsidian Vault as a Handoff Journal.

Creates:
1. Central Handoff Journal: '20-CLIENTS/Mijozlar_Muloqot_va_Handoff_Jurnali.md'
2. Per-client cards or appends to existing cards in '20-CLIENTS/<ClientName>/<ClientName>.md'.

Usage:
  python scripts/sync_utc_calls_to_obsidian_handoff.py
"""
from __future__ import annotations

import glob
import json
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

sys.stdout.reconfigure(encoding="utf-8")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ObsidianClientHandoff")

_ROOT = Path(__file__).resolve().parent.parent
VAULT_PATH = Path(r"C:\Users\baxti\OneDrive\Документы\Obsidian Vault")
CLIENTS_DIR = VAULT_PATH / "20-CLIENTS"
CENTRAL_JOURNAL = CLIENTS_DIR / "Mijozlar_Muloqot_va_Handoff_Jurnali.md"


def sanitize_filename(name: str) -> str:
    clean = re.sub(r'[\\/*?:"<>|]', "", name).strip()
    return clean or "Noma'lum Mijoz"


def load_candidate_deals() -> List[Dict[str, Any]]:
    deals = []
    files = glob.glob(str(_ROOT / "data" / "utc_analysis" / "deals" / "*.json"))
    for fpath in files:
        with open(fpath, encoding="utf-8") as f:
            d = json.load(f)
            phone = str(d.get("phone", "")).strip()
            if not phone or phone == "Raqam yo'q" or len("".join(c for c in phone if c.isdigit())) < 7:
                continue

            strat = d.get("amocrm_strategy", {})
            bant = d.get("bant_analysis", {})
            priority = str(strat.get("priority", "Noma'lum"))
            real_status = str(d.get("real_status", "Noma'lum"))
            dur = d.get("total_duration_sec", 0)

            score = 0
            if "p1" in priority.lower() or "yuqori" in priority.lower():
                score += 100
            elif "p2" in priority.lower() or "o'rta" in priority.lower():
                score += 50
            if "issiq" in real_status.lower() or "potensial_issiq" in real_status.lower():
                score += 50
            score += min(dur // 60, 40)

            clean_phone = "".join(c for c in phone if c.isdigit())
            if len(clean_phone) == 9:
                clean_phone = "998" + clean_phone

            deals.append({
                "card_no": d.get("card_no"),
                "client_name": d.get("client_name") or "Noma'lum",
                "phone": clean_phone,
                "score": score,
                "utc_status": d.get("utc_status"),
                "real_status": real_status,
                "priority": priority,
                "duration_sec": dur,
                "need_and_context": d.get("need_and_context", ""),
                "bant": bant,
                "operator_errors": d.get("operator_errors", []),
                "client_objections": d.get("client_objections", []),
                "opening_hook": strat.get("call_opening_hook", ""),
                "closing_pitch": strat.get("closing_pitch", ""),
                "target_stage": strat.get("target_stage", "Qayta aloqa"),
                "summary_uz": d.get("summary_uz", "")
            })

    deals.sort(key=lambda x: x["score"], reverse=True)
    return deals


def format_handoff_entry(d: Dict[str, Any], date_str: str = "2026-10-17") -> str:
    dur_min = d["duration_sec"] // 60
    dur_sec = d["duration_sec"] % 60
    bant = d.get("bant") or {}
    op_errors = "\n".join(f"  - {e}" for e in d.get("operator_errors", [])) or "  - Aniq xato qayd etilmadi"
    objs = "\n".join(f"  - {o}" for o in d.get("client_objections", [])) or "  - E'tiroz bildirilmadi"

    budget = bant.get("budget", "Noma'lum")
    authority = bant.get("authority", "Noma'lum")
    need = bant.get("need", "Noma'lum")
    timeline = bant.get("timeline", "Noma'lum")

    entry = f"""### 🗓️ {date_str} | [[{d['client_name']}]] (+{d['phone']})
- **Manba:** UTC Call-Center (Karta #{d['card_no']}, Oldingi status: `{d['utc_status']}`)
- **Suhbat davomiyligi:** {dur_min} daqiqa {dur_sec} soniya
- **Status:** `{d['real_status']}` | **Prioritet:** `{d['priority']}` | **amoCRM Bosqichi:** `{d['target_stage']}`

#### 🗣️ 1. Nimalar gaplashildi (Muhokama va Ehtiyoj)
- **Biznes va Ehtiyoj:** {d['need_and_context']}
- **Byudjet:** {budget}
- **Qaror qabul qiluvchi:** {authority}
- **Ehtiyoj darajasi:** {need}
- **Kutilayotgan muddat:** {timeline}

#### 🤝 2. Nimalarga kelishildi (Kelishuvlar va Takliflar)
- **Yopish taklifi (Closing Pitch):** {d['closing_pitch']}
- **Umumiy kelishuv xulosasi:** {d['summary_uz']}

#### ⚠️ 3. E'tirozlar va Operator Xatolari
- **Mijoz e'tirozlari / xavotirlari:**
{objs}
- **Oldingi operator xatolari (UTC):**
{op_errors}

#### 🚀 4. Keyingi qadam (Closer Kirish Guki va Vazifa)
- **Mas'ul:** [[Sotuv bo'limi]] (Closer)
- **Muddat:** Dushanba, 10:00
- **Kirish guki (Aynan shu gap bilan boshlang):**
  > *"{d['opening_hook']}"*

---
"""
    return entry


def sync_to_obsidian():
    if not CLIENTS_DIR.exists():
        logger.error(f"20-CLIENTS path not found: {CLIENTS_DIR}")
        return

    deals = load_candidate_deals()
    # Take top 35 hot deals
    hot_deals = [d for d in deals if d["score"] >= 90][:35]

    logger.info(f"Syncing {len(hot_deals)} client handoff entries to Obsidian...")

    journal_header = f"""---
title: "Mijozlar Muloqot va Handoff Jurnali"
type: handoff-log
tags: [crm, handoff, jonbranding, clients, sales]
updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}
---

# 📋 Mijozlar Muloqot va Handoff Jurnali (Jon Branding)

> Ushbu jurnalda har bir mijoz bilan bo'lib o'tgan oxirgi suhbat, muhokama qilingan masalalar, erishilgan kelishuvlar, mijoz e'tirozlari hamda keyingi aniq qadamlar (Handoff) xronologik tartibda muhrlanadi.
> **Qoida:** Har bir yangi suhbatdan so'ng ushbu faylga yangi blok qo'shiladi va tegishli mijoz kartochkasiga bog'lanadi.

---

## ⚡ So'nggi Suhbatlar va Handofflar Tarixi

"""

    journal_entries = []
    synced_clients = 0

    for d in hot_deals:
        entry = format_handoff_entry(d)
        journal_entries.append(entry)

        # Also sync to individual client card in 20-CLIENTS/<ClientName>/<ClientName>.md
        safe_name = sanitize_filename(d["client_name"])
        client_dir = CLIENTS_DIR / safe_name
        client_file = client_dir / f"{safe_name}.md"

        if not client_file.exists():
            # Check case-insensitive match
            for p in CLIENTS_DIR.glob(f"*{safe_name}*"):
                if p.is_dir():
                    cand = p / f"{p.name}.md"
                    if cand.exists():
                        client_file = cand
                        break

        if client_file.exists():
            try:
                content = client_file.read_text(encoding="utf-8")
                if "## 📝 Qaydlar va Kelishuvlar" in content:
                    # append under Qaydlar va Kelishuvlar
                    marker = "## 📝 Qaydlar va Kelishuvlar"
                    idx = content.find(marker) + len(marker)
                    new_content = content[:idx] + "\n\n" + entry + content[idx:]
                    client_file.write_text(new_content, encoding="utf-8")
                    logger.info(f"Updated client card: {client_file.name}")
                    synced_clients += 1
            except Exception as e:
                logger.error(f"Failed updating client card {client_file}: {e}")
        else:
            # Create fresh client dossier card
            client_dir.mkdir(parents=True, exist_ok=True)
            card_content = f"""---
title: "{safe_name}"
type: client-dossier
brand: "{safe_name}"
phone: "+{d['phone']}"
tags: [client, jonbranding, p1-hot]
services: [Branding, Trademark, Logo]
---

# 👤 {safe_name}

> **🎯 Xizmat:** [[Branding]] | **👥 Mas'ul:** [[Sotuv bo'limi]] | **⭐ Prioritet:** {d['priority']}

## 📌 Asosiy Ma'lumotlar & Kontaktlar
- **🏢 Mijoz / Brend:** `{safe_name}`
- **📞 Telefon:** `+{d['phone']}`
- **🏷️ Holat:** {d['real_status']} (amoCRM: `{d['target_stage']}`)

## 📝 Qaydlar va Kelishuvlar (Handoff Tarixi)

{entry}
"""
            try:
                client_file.write_text(card_content, encoding="utf-8")
                logger.info(f"Created new client card: {client_file.name}")
                synced_clients += 1
            except Exception as e:
                logger.error(f"Failed creating client card {client_file}: {e}")

    # Write central journal
    full_journal = journal_header + "\n".join(journal_entries)
    CENTRAL_JOURNAL.write_text(full_journal, encoding="utf-8")
    logger.info(f"Central Handoff Journal written: {CENTRAL_JOURNAL}")
    print(f"🎉 MUVAFFAQISATLI YAKUNLANDI!")
    print(f"• Markaziy Jurnal: {CENTRAL_JOURNAL}")
    print(f"• Yangilangan / Yaratilgan mijoz kartochkalari: {synced_clients} ta")


if __name__ == "__main__":
    sync_to_obsidian()

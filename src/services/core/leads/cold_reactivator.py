"""
AmoCRM Sovuq Baza Reaktivatsiyasi (Cold Lead Reactivator).

Eski sovub qolgan yoki yopilgan bitimlarni tahlil qilib:
1. Mijoz tarixi (avvalgi muloqot, ehtiyoj, to'xtab qolish sababi)
2. U bilan qanday munosabat o'rnatish kerakligi (yondashuv, salomlashish, taklif)
bo'yicha chuqur tahlil tayyorlaydi va 'Yangi LEads' bosqichiga eslatma (Note) bilan tushiradi.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from src.services.core.crm.amocrm.sync import AmoCRMSync
from src.services.core.crm.amocrm_pipeline_config import (
    REACTIVATION_PIPELINE_ID,
    SALES_NEW_STATUS_ID,
    SALES_PIPELINE_ID,
)

logger = logging.getLogger("cold_reactivator")

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_STORE_FILE = _PROJECT_ROOT / "data" / "reactivated_cold_leads.json"


def _load_seen_leads() -> set[int]:
    if not _STORE_FILE.exists():
        return set()
    try:
        with open(_STORE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return set(data.get("seen_ids", []))
    except Exception as e:
        logger.warning(f"[COLD_REACTIVATOR] Deduplikatsiya faylini o'qishda xato: {e}")
        return set()


def _save_seen_leads(seen: set[int]) -> None:
    os.makedirs(_STORE_FILE.parent, exist_ok=True)
    try:
        with open(_STORE_FILE, "w", encoding="utf-8") as f:
            json.dump({"seen_ids": sorted(list(seen)), "updated_at": datetime.now(timezone.utc).isoformat()}, f, indent=2)
    except Exception as e:
        logger.warning(f"[COLD_REACTIVATOR] Deduplikatsiya faylini saqlashda xato: {e}")


def extract_lead_notes_summary(notes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Bitim eslatmalaridan suhbatlar, AI tahlillari va kontekstni ajratish."""
    call_analyses = []
    forms = []
    general = []
    previous_manager = None

    for n in notes:
        text = str(n.get("params", {}).get("text") or n.get("text") or "").strip()
        if not text:
            continue

        text_lower = text.lower()
        if "shahnozaman" in text_lower or "shahnoza siz bilan" in text_lower or "shahnoza edim" in text_lower:
            previous_manager = "Shahnoza"
        elif "rayxon" in text_lower or "rayhona" in text_lower:
            previous_manager = "Rayxona"

        if "[AI_CALL_ANALYSIS]" in text:
            call_analyses.append(text)
        elif "Facebook Lead Ads" in text or "Forma savol-javoblari" in text:
            forms.append(text)
        else:
            general.append(text)

    return {
        "call_analyses": call_analyses,
        "forms": forms,
        "general": general,
        "previous_manager": previous_manager,
    }


def synthesize_client_playbook(
    lead_name: str,
    contact_name: str,
    phone: str,
    summary: Dict[str, Any],
) -> str:
    """Mijoz tarixi va u bilan qanday munosabat o'rnatish strategiyasini tuzish."""
    call_texts = "\n---\n".join(summary["call_analyses"][:3])
    form_texts = "\n".join(summary["forms"][:2])
    manager_mention = summary.get("previous_manager") or "Noma'lum"

    prompt_context = f"""
Mijoz ismi: {contact_name or lead_name}
Telefon: {phone or "Noma'lum"}
Avvalgi menejer: {manager_mention}

Forma ma'lumotlari:
{form_texts or "Mavjud emas"}

Oldingi qo'ng'iroq tahlillari:
{call_texts or "Qo'ng'iroq tahlili topilmadi"}
"""
    # Deterministic fallback agar AI kalit bo'lmasa yoki xato bersa
    return _generate_ai_or_rule_playbook(prompt_context, contact_name or lead_name, manager_mention, summary)


def _generate_ai_or_rule_playbook(context: str, name: str, manager: str, summary: Dict[str, Any]) -> str:
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=gemini_key)
            system_prompt = (
                "Siz Jon Branding premium branding agentligining yetakchi savdo strategisiz. "
                "Berilgan mijoz tarixi asosida sotuvchilar uchun qisqa, aniq va amaliy yo'riqnoma tuzing. "
                "Format qat'iy ravishda 2 ta bo'limdan iborat bo'lsin:\n"
                "1. 📜 MIJOZ TARIXI (Qachon nima bilan murojaat qilgan, ehtiyoji nima bo'lgan, nega to'xtab qolgan)\n"
                "2. 🎯 MUNOSABAT O'RNATISH STRATEGIYASI (Salomlashish matni, og'riqli nuqtaga yechim, qaysi taklif bilan chiqish kerak)"
            )
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=f"Ushbu sovuq mijoz ma'lumotlari:\n{context}\n\nIltimos, yo'riqnomani tuzing:",
                config=types.GenerateContentConfig(system_instruction=system_prompt, temperature=0.3),
            )
            if response.text:
                return response.text.strip()
        except Exception as e:
            logger.warning(f"[COLD_REACTIVATOR] Gemini generatsiyasida xato, qoidaga asoslanganiga o'tilmoqda: {e}")

    # Qoidaga asoslangan boyitilgan playbook
    history_lines = []
    if summary["forms"]:
        history_lines.append("• Murojaat manbasi: Reklama arizasi (Meta Lead Ads / Sayt).")
    if summary["call_analyses"]:
        history_lines.append(f"• Avvalgi suhbatlar: {len(summary['call_analyses'])} ta qo'ng'iroq tahlili mavjud.")
    if manager != "Noma'lum":
        history_lines.append(f"• Avval bog'langan menejer: {manager}.")

    return f"""### 📜 MIJOZ TARIXI
• Mijoz: {name}
{chr(10).join(history_lines) if history_lines else "• Avval branding va patentlash xizmatlari bilan qiziqqan, ammo qaror qabul qilish to'xtab qolgan."}

### 🎯 U BILAN QANDAY MUNOSABAT O'RNATISH KERAK
1. **Salomlashish va Kirish**:
   "Assalomu alaykum, {name}! Jon Branding agentligidan bezovta qilyapmiz. Avval loyihangiz bo'yicha bog'langan edik, hozir ishlar qanday ketyapti?"
2. **Yondashuv**:
   Eski narx yoki taklifni to'g'ridan-to'g'ri tiqishtirmasdan, biznesidagi o'zgarishlar va yangiliklarni so'rab, yangi amaldagi keyslarni ulashish.
3. **Keyingi Qadam**:
   15 daqiqalik bepul tahlil yoki loyiha auditi orqali muloqotni tiklash.
"""


class ColdLeadReactivator:
    """AmoCRM sovuq bazasini yangi leadlarga aylantiruvchi servis."""

    def __init__(self, amo: Optional[AmoCRMSync] = None):
        self.amo = amo or AmoCRMSync()

    def fetch_candidate_cold_leads(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Reactivation va Lost voronkalaridan eng munosib sovuq leadlarni olish."""
        headers = self.amo._get_headers()
        seen = _load_seen_leads()
        seen_candidate_ids = set()

        candidates = []
        # 1. Reactivation voronkasi (10947042)
        url = f"{self.amo.base_url}/api/v4/leads"
        params = {
            "filter[pipeline_id]": REACTIVATION_PIPELINE_ID,
            "limit": 50,
            "with": "contacts",
        }
        try:
            r = requests.get(url, headers=headers, params=params, timeout=30)
            if r.status_code == 200:
                leads = r.json().get("_embedded", {}).get("leads", [])
                for l in leads:
                    lid = l.get("id")
                    if lid not in seen and lid not in seen_candidate_ids and l.get("_embedded", {}).get("contacts"):
                        candidates.append(l)
                        seen_candidate_ids.add(lid)
                        if len(candidates) >= limit:
                            return candidates
        except Exception as e:
            logger.error(f"[COLD_REACTIVATOR] Reactivation o'qishda xato: {e}")

        # 2. Agar yetmasa, Sotuv voronkasidagi Yopilgan (143) bitimlardan eng yangilari
        if len(candidates) < limit:
            params_lost = {
                "filter[pipeline_id]": SALES_PIPELINE_ID,
                "filter[statuses][0][status_id]": 143,
                "limit": 50,
                "with": "contacts",
            }
            try:
                r2 = requests.get(url, headers=headers, params=params_lost, timeout=30)
                if r2.status_code == 200:
                    leads2 = r2.json().get("_embedded", {}).get("leads", [])
                    leads2.sort(key=lambda x: x.get("updated_at", 0), reverse=True)
                    for l in leads2:
                        lid = l.get("id")
                        if lid not in seen and lid not in seen_candidate_ids and l.get("_embedded", {}).get("contacts"):
                            candidates.append(l)
                            seen_candidate_ids.add(lid)
                            if len(candidates) >= limit:
                                break
            except Exception as e:
                logger.error(f"[COLD_REACTIVATOR] Lost leads o'qishda xato: {e}")

        return candidates[:limit]

    def reactivate_lead(self, orig_lead: Dict[str, Any]) -> Optional[int]:
        """Bitta sovuq leadni to'liq tahlil qilib, Yangi LEads ga tushirish."""
        headers = self.amo._get_headers()
        orig_id = orig_lead.get("id")
        orig_name = orig_lead.get("name") or "Sovuq baza mijoz"

        contacts = orig_lead.get("_embedded", {}).get("contacts", [])
        if not contacts:
            logger.warning(f"[COLD_REACTIVATOR] Lead #{orig_id} da kontakt yo'q, skip.")
            return None

        primary_contact_id = contacts[0]["id"]

        # Notes olish
        notes_url = f"{self.amo.base_url}/api/v4/leads/{orig_id}/notes"
        r_notes = requests.get(notes_url, headers=headers, timeout=20)
        notes = r_notes.json().get("_embedded", {}).get("notes", []) if r_notes.status_code == 200 else []

        # Kontakt notes ham olish
        c_notes_url = f"{self.amo.base_url}/api/v4/contacts/{primary_contact_id}/notes"
        r_cnotes = requests.get(c_notes_url, headers=headers, timeout=20)
        if r_cnotes.status_code == 200:
            notes.extend(r_cnotes.json().get("_embedded", {}).get("notes", []))

        summary = extract_lead_notes_summary(notes)

        # Kontakt ma'lumotini olish
        c_url = f"{self.amo.base_url}/api/v4/contacts/{primary_contact_id}"
        r_c = requests.get(c_url, headers=headers, timeout=20)
        c_data = r_c.json() if r_c.status_code == 200 else {}
        contact_name = c_data.get("name", "")
        phone = ""
        for cf in c_data.get("custom_fields_values", []) or []:
            if cf.get("field_code") == "PHONE" or "telefon" in cf.get("field_name", "").lower():
                vals = cf.get("values", [])
                if vals:
                    phone = str(vals[0].get("value", ""))
                    break

        playbook_text = synthesize_client_playbook(orig_name, contact_name, phone, summary)

        # Yangi bitim payload
        new_tags = ["Sovuq_Baza", "Reactivation"]

        payload = {
            "name": f"{orig_name} (Qayta uyg'otish)",
            "pipeline_id": SALES_PIPELINE_ID,
            "status_id": SALES_NEW_STATUS_ID,
            "price": orig_lead.get("price") or 0,
            "_embedded": {
                "contacts": [{"id": primary_contact_id}],
                "tags": [{"name": t} for t in new_tags],
            },
        }

        # Yaratish
        create_url = f"{self.amo.base_url}/api/v4/leads"
        try:
            resp = requests.post(create_url, headers=headers, json=[payload], timeout=30)
            if resp.status_code in (200, 201):
                new_lead = resp.json().get("_embedded", {}).get("leads", [{}])[0]
                new_id = new_lead.get("id")

                # Primechaniya (Note) qo'shish
                note_payload = [{"note_type": "common", "params": {"text": playbook_text}}]
                requests.post(f"{self.amo.base_url}/api/v4/leads/{new_id}/notes", headers=headers, json=note_payload, timeout=20)

                seen = _load_seen_leads()
                seen.add(orig_id)
                _save_seen_leads(seen)

                logger.info(f"[COLD_REACTIVATOR] Yangi bitim #{new_id} muvaffaqiyatli yaratildi (Asl #{orig_id}).")
                return new_id
            logger.error(f"[COLD_REACTIVATOR] Bitim ochishda xato: {resp.status_code} {resp.text}")
            return None
        except Exception as e:
            logger.error(f"[COLD_REACTIVATOR] Exception: {e}")
            return None

    def run_batch(self, count: int = 5) -> Dict[str, Any]:
        """Belgilangan miqdordagi sovuq leadlarni reaktivatsiya qilish."""
        candidates = self.fetch_candidate_cold_leads(limit=count)
        created = []
        for l in candidates:
            new_id = self.reactivate_lead(l)
            if new_id:
                created.append({"original_id": l.get("id"), "new_id": new_id, "name": l.get("name")})
            asyncio.run(asyncio.sleep(0.5))

        return {"candidates_found": len(candidates), "created_count": len(created), "leads": created}

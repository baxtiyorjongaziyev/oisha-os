"""
AI Outreach campaign generator for archived leads.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Dict, List

import src.config as config

logger = logging.getLogger("crm_archiver")


async def generate_outreach_campaign(
    lead: Dict[str, Any],
    phone: str,
    contact_name: str,
    notes: List[Dict[str, Any]],
) -> Dict[str, str]:
    lead_name = lead.get("name", "Noma'lum")
    price = lead.get("price", 0)
    custom_fields = lead.get("custom_fields_values", []) or []

    cf_desc = []
    for cf in custom_fields:
        name = cf.get("field_name", "")
        vals = [str(v.get("value", "")) for v in cf.get("values", [])]
        cf_desc.append(f"{name}: {', '.join(vals)}")

    notes_desc = []
    for n in notes[:10]:
        text = n.get("params", {}).get("text", "") or n.get("text", "")
        if text:
            notes_desc.append(text)

    context_prompt = f"""
    Bitim nomi: {lead_name}
    Mijoz ismi: {contact_name or "Noma'lum"}
    Telefon: {phone or "Noma'lum"}
    Narxi: {price:,} so'm
    Maxsus maydonlar:
    {chr(10).join(cf_desc)}

    Suhbat tarixi/Izohlar:
    {chr(10).join(notes_desc)}
    """

    system_instruction = """
    Siz Jon Branding premium branding agentligining (Oisha-OS) yetakchi outreach strategisiz.
    Vazifangiz: Mijoz bilan avvalgi muloqot va bitim kontekstini (tarixi, yozishmalar, izohlar) tahlil qilib, uni qayta uyg'otish (reactivation) uchun shaxsiy va juda yuqori konversiyali 3 bosqichli outreach xabarlarini o'zbek tilida (lotin alifbosida) tayyorlash.

    Talablar:
    1. Tone: Premium, o'ta samimiy, insoniy, hurmat bilan (VIP ton). Hech qanday robotlik yoki andozaviy bot iboralari bo'lmasin. Baxtiyorjon aka yoki agentlik PM-lari nomidan yoziladi.
    2. Har bir xabar mijozning ismini va original qiziqishini (masalan, Naming, Logo, Brandbook, SMM yoki Web) hisobga olsin.
    3. Format: Natijani faqat va faqat quyidagi JSON formatida qaytaring, boshqa hech qanday so'z yoki tushuntirish qo'shmang:
    {
      "step1": "1-bosqich xabari matni...",
      "step2": "2-bosqich xabari matni...",
      "step3": "3-bosqich xabari matni..."
    }
    """

    api_key = os.getenv("GEMINI_API_KEY") or getattr(config, "GEMINI_API_KEY", "")
    if not api_key:
        logger.warning("[ARCHIVER] GEMINI_API_KEY topilmadi. Standart outreach xabarlar ishlatiladi.")
        return {
            "step1": f"Assalomu alaykum, {contact_name or 'Mijoz'}. Jon Branding agentligidan bezovta qilyapmiz. Loyihangiz bo'yicha qanday yangiliklar bor?",
            "step2": "Sizga yaqinda amalga oshirgan yangi keyslarimizni ulashmoqchi edik. Ko'rib chiqish qiziqmi?",
            "step3": "Branding masalalarini qisqa 15 daqiqalik qo'ng'iroqda muhokama qila olamiz. Sizga qaysi kun qulay?",
        }

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        model_name = os.getenv("GEMINI_CALL_MODEL", "gemini-2.0-flash")
        if model_name.startswith("models/"):
            model_name = model_name.replace("models/", "", 1)

        prompt = f"Mijoz va bitim konteksti:\n{context_prompt}\n\nIltimos, outreach xabarlarini yuqoridagi system instruction talablariga mos ravishda JSON ko'rinishida generatsiya qiling."
        loop = asyncio.get_event_loop()

        response = await loop.run_in_executor(
            None,
            lambda: client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                ),
            ),
        )

        text = response.text or ""
        data = json.loads(text.strip())
        return {
            "step1": data.get("step1", "").strip(),
            "step2": data.get("step2", "").strip(),
            "step3": data.get("step3", "").strip(),
        }
    except Exception as e:
        logger.error(f"[ARCHIVER AI ERROR] Outreach yaratishda xato: {e}")
        return {
            "step1": f"Assalomu alaykum, {contact_name or 'Mijoz'}. Jon Branding agentligidan bezovta qilyapmiz. Loyihangiz bo'yicha qanday yangiliklar bor?",
            "step2": "Sizga yaqinda amalga oshirgan yangi keyslarimizni ulashmoqchi edik. Ko'rib chiqish qiziqmi?",
            "step3": "Branding masalalarini qisqa 15 daqiqalik qo'ng'iroqda muhokama qila olamiz. Sizga qaysi kun qulay?",
        }

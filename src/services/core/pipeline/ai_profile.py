"""
AI customer intelligence profile generation for pipeline auditor.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger()


async def generate_intelligence_profile(
    genai_client: Any,
    model_name: str,
    deal_info: Dict[str, Any],
    dm_history: List[Dict[str, Any]],
    call_history: List[Dict[str, Any]],
    airtable_project: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    history_snippet = "No chat history logged."
    if dm_history:
        history_snippet = "\n".join(
            [
                f"{'Oisha (AI)' if m.get('is_ai_reply') else 'Mijoz'}: {m.get('message_text', '')}"
                for m in dm_history[-20:]
            ]
        )

    call_snippet = "No call recordings analyzed."
    if call_history:
        call_snippet = "\n".join(
            [
                f"Call Summary: {c.get('summary', '')}\n"
                f"Mood: {c.get('client_mood', '')}\n"
                f"Transcript:\n{c.get('transcript', '')[:1000]}"
                for c in call_history[-5:]
            ]
        )

    airtable_snippet = "No operational project found in Airtable."
    if airtable_project:
        airtable_snippet = (
            f"Project Name: {airtable_project.get('project_name')}\n"
            f"Stage: {airtable_project.get('stage')}\n"
            f"Deadline: {airtable_project.get('deadline')}\n"
            f"PM/Owner: {airtable_project.get('pm')}"
        )

    prompt = (
        "Analyze the following cross-system customer data and generate a unified Customer Intelligence Profile in Uzbek.\n"
        "Identify:\n"
        "1. Client Psychotype: 'Analytical' (fakt va raqamlarni sevadi), 'Assertive' (tezkor va qat'iy), "
        "'Expressive' (hissiyotli va g'oyalarga boy), 'Amiable' (muloyim va munosabatga kirishuvchan).\n"
        "2. Buying Drivers: Brand identity, premium status, market growth, or cost efficiency.\n"
        "3. Key Pain Points and Objections raised in chat or phone calls.\n"
        "4. Win/Close Probability (0 to 100%).\n"
        "5. Strategic Next Task: A highly specific, extremely personalized, tactical NEXT action step (Zadacha) in Uzbek "
        "for the manager to follow up and progress this deal. This should be concrete, e.g., 'Jasurga logotip tekshiruvi narxini yuborish va patent shartnomasini taqdim etish'.\n"
        "6. Strategic Negotiation Plan: exactly 3 specific tactical action steps for the manager to close or win this deal.\n\n"
        "Ensure the output is valid JSON, strictly complying with the following structure:\n"
        "{\n"
        '  "psychotype": "Analytical / Assertive / Expressive / Amiable",\n'
        '  "pain_points": "Extract client\'s real pain points in Uzbek",\n'
        '  "objections": "Objections raised and how to address them in Uzbek",\n'
        '  "buying_drivers": "Key buying drivers in Uzbek",\n'
        '  "close_probability": 85,\n'
        '  "next_task_text": "A highly personalized next action task in Uzbek based on calls and chat history",\n'
        '  "negotiation_strategy": "1. Birinchi qadam...\\n2. Ikkinchi qadam...\\n3. Uchinchi qadam..."\n'
        "}\n\n"
        f"--- AmoCRM Deal Info ---\n"
        f"Deal Name: {deal_info.get('name')}\n"
        f"Price: {deal_info.get('price')} so'm\n"
        f"Status ID: {deal_info.get('status_id')}\n\n"
        f"--- Airtable Project Status ---\n"
        f"{airtable_snippet}\n\n"
        f"--- AmoCRM Call Recordings ---\n"
        f"{call_snippet}\n\n"
        f"--- Telegram DM History ---\n"
        f"{history_snippet}"
    )

    try:
        from google.genai import types
        from src.services.utils.gemini_fallback import generate_content_with_fallback

        response, _ = await generate_content_with_fallback(
            genai_client,
            primary_model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
            ),
            env_name="GEMINI_PIPELINE_AUDITOR_FALLBACK_MODELS",
            log_prefix="[AUDITOR]",
        )
        raw_text = (response.text or "").strip()
        return json.loads(raw_text)
    except Exception as e:
        logger.error(f"[AUDITOR] AI profile generation error: {e}")
        return {
            "psychotype": "Amiable",
            "pain_points": "N/A",
            "objections": "N/A",
            "buying_drivers": "Quality",
            "close_probability": 50,
            "next_task_text": "Mijoz bilan aloqaga chiqish va ehtiyojlarni aniqlash",
            "negotiation_strategy": "1. Muloqotni tiklash\n2. Ehtiyojlarni aniqlash\n3. Taklif berish",
        }

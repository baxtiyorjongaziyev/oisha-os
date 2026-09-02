import asyncio
from typing import Any, Dict, Optional
import structlog
from src.services.core.sales_playbook import (
    IDEAL_CLIENT_TALK_PCT,
    outcome_prompt_uz,
    rubric_prompt_uz,
)
from src.time_utils import get_local_now
from src.services.call_analytics.helpers import *

logger = structlog.get_logger()

class CallScorerMixin:
    async def analyze_transcript(
        self,
        transcript: str,
        duration_seconds: int = 0,
        omnichannel_context: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Classify, summarize, and extract next steps from transcript + CRM & Telegram context."""
        if not transcript:
            return self._fallback_analysis(transcript)

        try:
            from google.genai import types

            client_pct, agent_pct, attributed = _speaker_split(transcript)
            ratio_line = (
                f"  Mijoz: {client_pct}%  |  Sotuvchi: {agent_pct}%\n"
                if attributed
                else "  Aniqlanmadi — transkripsiyada rollar belgilanmagan.\n"
            )
            now_local = get_local_now()

            crm_block = ""
            if omnichannel_context and hasattr(omnichannel_context, "format_crm_prompt_block"):
                crm_block = f"\nAMOCRM LID VA KONTAKT MAYDONLARI:\n{omnichannel_context.format_crm_prompt_block()}\n"

            tg_block = ""
            if omnichannel_context and hasattr(omnichannel_context, "format_telegram_prompt_block"):
                tg_block = f"\nTELEGRAM YOZISHMALAR TARIXI (Ushbu mijoz bilan oxirgi xabarlar):\n{omnichannel_context.format_telegram_prompt_block()}\n"

            prompt = (
                "Quyidagi telefon suhbati transkripsiyasini va unga biriktirilgan mijoz kontekstini "
                "(AmoCRM kartochka maydonlari hamda Telegram yozishmalari) professional savdo tahlilchisi sifatida "
                "birlashtirgan holda 360-darajali to'liq tahlil qiling.\n\n"
                f"HOZIRGI SANA VA VAQT (Toshkent): {now_local.strftime('%Y-%m-%d %H:%M')} "
                f"({_WEEKDAY_UZ[now_local.weekday()]})\n"
                "Transkripsiyada nisbiy vaqt aytilsa (\"ertaga\", \"peshin\", \"kelasi hafta\", "
                "\"dushanba\"), shu hozirgi sanaga nisbatan hisoblang.\n"
                f"{crm_block}"
                f"{tg_block}\n"
                "TOIFALAR (faqat bittasini tanlang):\n"
                "- Shaxsiy: shaxsiy, biznesga aloqasi yo'q suhbat.\n"
                "- Oila: oila a'zolari, uy ishlari, bolalar yoki qarindoshlar haqida.\n"
                "- Jamoa: xodimlar, ichki ishlar, vazifa, deadline, operatsion muhokama.\n"
                "- Mijoz: brending, dizayn, SMM, sayt, loyiha, narx, savdo yoki mijoz muzokarasi.\n"
                "- Boshqa: aralash, spam yoki yuqoridagilarga aniq kirmaydigan qo'ng'iroq.\n\n"
                "GAPIRISH NISBATI (hisoblangan):\n"
                f"{ratio_line}"
                f"  Ideal: mijoz ≥{IDEAL_CLIENT_TALK_PCT}%.\n\n"
                f"{rubric_prompt_uz()}\n"
                f"{outcome_prompt_uz()}\n"
                "Rubrik faqat Mijoz toifasiga taalluqli. Agar toifa Mijoz emas "
                "(Shaxsiy, Oila, Jamoa, Boshqa) bo'lsa — rubrik_baholar uchun "
                "umumiy muloqot sifatiga qarab baholang.\n\n"
                "Javobni faqat JSON formatida qaytaring:\n"
                "{\n"
                '  "summary": "2-4 gapda O\'zbekcha yaxlit 360° xulosa (telefon suhbati, Telegramdagi avvalgi yozishmalar va CRM maydonlarini bir-biriga bog\'lagan holda)",\n'
                '  "category": "Shaxsiy|Oila|Jamoa|Mijoz|Boshqa",\n'
                '  "client_mood": "Ijobiy|Neytral|Salbiy|Noaniq",\n'
                '  "next_steps": "Keyingi aniq qadamlar yoki N/A",\n'
                '  "keyingi_kelishuv": "Mijoz bilan aynan nima haqida kelishildi (masalan: \'Ertaga soat 15:00 da taklif yuborish va qayta qo\'ng\'iroq qilish\')",\n'
                '  "kelishilgan_vaqt": "Agar suhbatda aniq kun/soat kelishilgan bo\'lsa '
                '(masalan \'ertaga soat 15da\', \'dushanba peshin\'), uni YYYY-MM-DD HH:MM '
                'formatida yozing (hozirgi sanaga nisbatan hisoblab). Aniq vaqt aytilmagan '
                'bo\'lsa — null.",\n'
                f'  "client_talk_pct": {client_pct},\n'
                f'  "agent_talk_pct": {agent_pct},\n'
                '  "lead_bahosi": <0-100: lead potensiali — qiziqish, byudjet, qaror qabul qilish>,\n'
                '  "suhbat_oilasi": "Ehtiyoj aniqlash|Yechim taqdimoti|Narx muhokamasi|Follow-up|Shartnoma|Boshqa",\n'
                '  "suhbat_domeni": "Savdo|Mijoz xizmati|Loyiha muhokamasi|Texnik|Boshqa",\n'
                '  "baholash_rejimi": "Savdo playbook boyicha baholanadi|Xizmat standarti|Loyiha boshqaruvi|Boshqa",\n'
                '  "biznes_mosligi": "Biznesga mos|Qisman mos|Mos emas",\n'
                '  "servis_yonalishi": "Brending|Dizayn|SMM|Sayt|Biznes transformatsiya|Reklama|Boshqa",\n'
                '  "mijoz_lavozimi": "lavozim yoki N/A",\n'
                '  "mijoz_kompaniya": "kompaniya nomi yoki N/A",\n'
                '  "qaror_qabul_qiluvchi": "Ha|Yoq|Noaniq",\n'
                '  "joylashuv": "shahar/viloyat yoki N/A",\n'
                '  "mijoz_malumotlari": ["mijoz haqida muhim ma\'lumot 1", "muhim ma\'lumot 2"],\n'
                '  "natija": "yuqoridagi natija kalitlaridan bittasi",\n'
                '  "uzilish_vaqti": "Agar suhbat biror lahzada BUZILGAN bo\'lsa '
                '(mijoz qiziqishdan qolgan, e\'tiroz javobsiz qolgan, savdo uzilgan) '
                '— o\'sha gapning vaqt belgisini \"mm:ss\" formatida yozing. '
                'Suhbat yaxshi ketgan yoki lahzani aniqlab bo\'lmasa — null.",\n'
                '  "uzilish_sababi": "Uzilish lahzasida AYNAN nima noto\'g\'ri ketdi '
                '(masalan: \"Ehtiyoj aniqlanmadi\", \"E\'tirozga javob berilmadi\"). '
                'uzilish_vaqti null bo\'lsa — null.",\n'
                '  "kuchli_tomonlar": ["menejer aynan nimani YAXSHI qildi (1-3 ta, aniq)"],\n'
                '  "zaif_tomonlar": ["menejer nimani o\'tkazib yubordi yoki xato qildi '
                '(1-3 ta, aniq va tuzatib bo\'ladigan)"],\n'
                '  "konversiya_tavsiyalari": ["sotuvchiga bitimni yutish va konversiyani oshirish bo\'yicha 1-3 ta aniq amaliy taktik maslahat"],\n'
                '  "etirozlar": ["mijoz bildirgan e\'tirozlar, masalan \'qimmat\'"],\n'
                '  "rubrik_baholar": {\n'
                '    "salomlashish": {"ball": <0-100>},\n'
                '    "ehtiyojlar": {"ball": <0-100>},\n'
                '    "qiymat": {"ball": <0-100>},\n'
                '    "etirozlar": {"ball": <0-100>},\n'
                '    "yakunlash": {"ball": <0-100>},\n'
                '    "muloqot_sifati": {"ball": <0-100>}\n'
                '  }\n'
                "}\n\n"
                f"Transkripsiya:\n{transcript}"
            )
            response = await self._gemini_generate_content(
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )
            data = _extract_json_object(getattr(response, "text", "") or "")
            res = self._normalise_analysis(data, transcript, duration_seconds)
            if omnichannel_context:
                res["omnichannel_context"] = omnichannel_context
            return res
        except GeminiQuotaCooldownError:
            logger.info("[CALL] Gemini transcript analysis skipped during quota cooldown.")
            fallback_analysis = await self._analyze_transcript_openai(
                transcript, duration_seconds, omnichannel_context
            )
            if not fallback_analysis:
                fallback_analysis = await self._analyze_transcript_free_ai(
                    transcript, duration_seconds, omnichannel_context
                )
            if fallback_analysis:
                return fallback_analysis
            return self._fallback_analysis(transcript)
        except Exception as exc:
            logger.error("[CALL] Transcript analysis failed: %s", exc)
            fallback_analysis = await self._analyze_transcript_openai(
                transcript, duration_seconds, omnichannel_context
            )
            if not fallback_analysis:
                fallback_analysis = await self._analyze_transcript_free_ai(
                    transcript, duration_seconds, omnichannel_context
                )
            if fallback_analysis:
                return fallback_analysis
            return self._fallback_analysis(transcript)

    async def _analyze_transcript_openai(
        self,
        transcript: str,
        duration_seconds: int = 0,
        omnichannel_context: Optional[Any] = None,
    ) -> Optional[Dict[str, Any]]:
        """Fallback JSON analysis via OpenAI text model."""
        if not self.openai_client:
            return None

        model = getattr(self._settings, "OPENAI_TEXT_MODEL", "gpt-4o-mini")
        system = (
            "Siz O'zbek tilida ishlaydigan amoCRM qo'ng'iroq va omnichannel tahlilchisisiz. "
            "Faqat JSON qaytaring."
        )
        now_local = get_local_now()

        crm_block = ""
        if omnichannel_context and hasattr(omnichannel_context, "format_crm_prompt_block"):
            crm_block = f"\nCRM Maydonlari:\n{omnichannel_context.format_crm_prompt_block()}\n"

        tg_block = ""
        if omnichannel_context and hasattr(omnichannel_context, "format_telegram_prompt_block"):
            tg_block = f"\nTelegram Tarixi:\n{omnichannel_context.format_telegram_prompt_block()}\n"

        user = (
            "Telefon suhbati transkripsiyasini va mijozning CRM hamda Telegram kontekstini tahlil qiling.\n"
            f"Hozirgi sana va vaqt (Toshkent): {now_local.strftime('%Y-%m-%d %H:%M')}\n"
            f"{crm_block}"
            f"{tg_block}\n"
            "Toifalar: Shaxsiy, Oila, Jamoa, Mijoz, Boshqa.\n"
            "Kayfiyat: Ijobiy, Neytral, Salbiy, Noaniq.\n"
            "JSON schema: summary, category, client_mood, next_steps, keyingi_kelishuv, "
            "konversiya_tavsiyalari (array of 1-3 actionable advice), "
            "kelishilgan_vaqt (suhbatda aniq kun/soat kelishilgan bo'lsa "
            "\"YYYY-MM-DD HH:MM\" formatida, aks holda null).\n\n"
            f"Transkripsiya:\n{transcript}"
        )

        def _create():
            return self.openai_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )

        try:
            response = await asyncio.to_thread(_create)
            raw = response.choices[0].message.content if response.choices else ""
            data = _extract_json_object(raw or "")
            res = self._normalise_analysis(data, transcript, duration_seconds)
            if omnichannel_context:
                res["omnichannel_context"] = omnichannel_context
            return res
        except Exception as exc:
            logger.error("[CALL] OpenAI analysis fallback failed: %s", exc)
            return None

    async def _analyze_transcript_free_ai(
        self,
        transcript: str,
        duration_seconds: int = 0,
        omnichannel_context: Optional[Any] = None,
    ) -> Optional[Dict[str, Any]]:
        """Fallback JSON analysis via free_ai_router (Groq/Cloudflare text models)."""
        system = (
            "Siz O'zbek tilida ishlaydigan amoCRM qo'ng'iroq va omnichannel tahlilchisisiz. "
            "Faqat JSON qaytaring, boshqa matn yozmang."
        )
        now_local = get_local_now()

        crm_block = ""
        if omnichannel_context and hasattr(omnichannel_context, "format_crm_prompt_block"):
            crm_block = f"\nCRM Maydonlari:\n{omnichannel_context.format_crm_prompt_block()}\n"

        tg_block = ""
        if omnichannel_context and hasattr(omnichannel_context, "format_telegram_prompt_block"):
            tg_block = f"\nTelegram Tarixi:\n{omnichannel_context.format_telegram_prompt_block()}\n"

        prompt = (
            "Quyidagi telefon suhbati transkripsiyasini va unga biriktirilgan mijoz kontekstini "
            "professional savdo tahlilchisi sifatida yaxlit 360-darajali tahlil qiling.\n\n"
            f"HOZIRGI SANA VA VAQT (Toshkent): {now_local.strftime('%Y-%m-%d %H:%M')}\n"
            f"{crm_block}"
            f"{tg_block}\n"
            "TOIFALAR (faqat bittasini tanlang): Shaxsiy, Oila, Jamoa, Mijoz, Boshqa.\n"
            "Mijoz = brending, dizayn, SMM, sayt, loyiha, narx, savdo yoki mijoz muzokarasi.\n\n"
            f"{rubric_prompt_uz()}\n"
            f"{outcome_prompt_uz()}\n"
            "Rubrik faqat Mijoz toifasiga taalluqli. Boshqa toifalarda "
            "rubrik_baholar uchun umumiy muloqot sifatiga qarab baholang.\n\n"
            "Javobni faqat JSON formatida qaytaring:\n"
            "{\n"
            '  "summary": "2-4 gapda O\'zbekcha yaxlit 360° xulosa",\n'
            '  "category": "Shaxsiy|Oila|Jamoa|Mijoz|Boshqa",\n'
            '  "client_mood": "Ijobiy|Neytral|Salbiy|Noaniq",\n'
            '  "next_steps": "Keyingi aniq qadamlar yoki N/A",\n'
            '  "keyingi_kelishuv": "Kelishilgan aniq qadam",\n'
            '  "kelishilgan_vaqt": "Aniq kun/soat kelishilgan bo\'lsa YYYY-MM-DD HH:MM, aks holda null",\n'
            '  "natija": "yuqoridagi natija kalitlaridan bittasi",\n'
            '  "kuchli_tomonlar": ["menejer aynan nimani YAXSHI qildi (1-3 ta)"],\n'
            '  "zaif_tomonlar": ["menejer nimani o\'tkazib yubordi (1-3 ta)"],\n'
            '  "konversiya_tavsiyalari": ["konversiyani oshirish va savdoni yopish bo\'yicha 1-3 ta tavsiya"],\n'
            '  "etirozlar": ["mijoz bildirgan e\'tirozlar"],\n'
            '  "rubrik_baholar": {\n'
            '    "salomlashish": {"ball": <0-100>},\n'
            '    "ehtiyojlar": {"ball": <0-100>},\n'
            '    "qiymat": {"ball": <0-100>},\n'
            '    "etirozlar": {"ball": <0-100>},\n'
            '    "yakunlash": {"ball": <0-100>},\n'
            '    "muloqot_sifati": {"ball": <0-100>}\n'
            '  }\n'
            "}\n\n"
            f"Transkripsiya:\n{transcript}"
        )
        try:
            result = await self.free_ai_router.generate_text(
                prompt, system=system, max_tokens=1800, temperature=0.2
            )
            data = _extract_json_object(result.text if result else "")
            if not data:
                return None
            res = self._normalise_analysis(data, transcript, duration_seconds)
            if omnichannel_context:
                res["omnichannel_context"] = omnichannel_context
            return res
        except Exception as exc:
            logger.error("[CALL] free_ai_router analysis fallback failed: %s", exc)
            return None

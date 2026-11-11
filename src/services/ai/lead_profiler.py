"""
Oisha-OS: Telegram foydalanuvchisini toʻliq 360° tahlil qilish va dosye tuzish xizmati.

Telegram MTProto va Gemini AI imkoniyatlaridan foydalanib:
- Profil maʼlumotlari (Bio, Premium, Rasmlar, Umumiy guruhlar)
- Muloqot uslubi va psixologik portret
- Xarid qobiliyati va qaror qabul qiluvchilik (LPR) darajasini aniqlaydi.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from telethon import functions
from telethon.tl.functions.messages import GetCommonChatsRequest

from src.services.utils.gemini_fallback import generate_content_with_fallback
from src.settings import settings

logger = logging.getLogger("TelegramLeadProfiler")


@dataclass
class TelegramRawSignals:
    """Telegram MTProto orqali olingan birlamchi texnik maʼlumotlar."""
    user_id: int
    first_name: str = ""
    last_name: str = ""
    username: str = ""
    phone: str = ""
    about: str = ""  # Bio
    is_premium: bool = False
    is_verified: bool = False
    lang_code: str = "uz"
    photo_count: int = 0
    common_chats: List[str] = field(default_factory=list)
    has_business_profile: bool = False
    business_intro: str = ""
    online_status: str = "unknown"


@dataclass
class TelegramLeadProfile:
    """AI tomonidan sintez qilingan toʻliq mijoz profili va sotuv strategiyasi."""
    user_id: int
    full_name: str
    username: str
    phone: str
    is_premium: bool
    business_domain: str
    estimated_role: str  # "LPR (Rahbar/Asoschi)", "Menejer/Xodim", "Startapchi"
    psychological_type: str  # "Amaliyotchi (vaqti tigʻiz)", "Analitik (raqamlar muhim)", "Ikkilanuvchi"
    solvency_level: str  # "Yuqori (Enterprise)", "Oʻrtacha (Business)", "Startap/Past"
    communication_tip: str  # Menejer aynan qanday muloqot qilishi kerak
    recommended_package: str  # Tavsiya etiladigan Jon Branding xizmati
    key_icebreaker: str  # Muloqotni boshlash uchun eng zoʻr "muz yorar" mavzu
    ad_library_queries: List[str] = field(default_factory=list)  # Instagram/FB sahifalar

    def _ad_library_lines(self) -> List[str]:
        if not self.ad_library_queries:
            return []
        from src.services.core.marketing.ad_library_links import build_ad_library_url

        lines = ["", "📢 **Meta reklamalari (qoʻlda tekshiring):**"]
        for query in self.ad_library_queries:
            lines.append(f"👉 {query}: {build_ad_library_url(query)}")
        return lines

    def format_dossier(self) -> str:
        """Chiroyli formatlangan Telegram dosyesi."""
        premium_badge = "⭐️ Premium Akkaunt" if self.is_premium else "Oddiy Akkaunt"
        handle = f"@{self.username}" if self.username else "Usernamesiz"
        phone_str = f"+{self.phone}" if self.phone else "Yashiringan"

        lines = [
            f"👤 **TELEGRAM 360° MIJOZ DOSYESI | {self.full_name.upper()}**",
            "────────────────────────────────────────",
            f"📱 **Akkaunt:** {handle} | {phone_str} | {premium_badge}",
            f"🏢 **Faoliyat sohasi:** {self.business_domain}",
            f"👔 **Taxminiy lavozim:** {self.estimated_role}",
            f"🧠 **Psixologik toifa:** {self.psychological_type}",
            f"💰 **Toʻlov qobiliyati:** {self.solvency_level}",
            "",
            f"🧊 **Muz yorar mavzu (Icebreaker):**",
            f"👉 {self.key_icebreaker}",
            "",
            f"🎯 **Sotuvchiga tavsiya (Qanday gaplashish kerak?):**",
            f"👉 {self.communication_tip}",
            "",
            f"📦 **Tavsiya etiladigan xizmat paketi:**",
            f"👉 {self.recommended_package}",
            *self._ad_library_lines(),
            "────────────────────────────────────────",
        ]
        return "\n".join(lines)


_PROFILER_PROMPT = """Sen Jon Branding agentligining Bosh Kiber-Tahlilchisi va Profilerisan.
Quyida Telegram MTProto orqali olingan foydalanuvchi maʼlumotlari va uning yozgan xabarlari keltirilgan.

SENING VAZIFANG:
Ushbu shaxs haqida barcha signallarni tahlil qilib, sotuvchi uchun aniq mijoz dosyesini tuzish:
1. "business_domain" — Qaysi sohada faoliyat yuritadi (bio, guruhlar, xabarlardan aniqla)?
2. "estimated_role" — U LPR (rahbar, taʼsischi)mi yoki oddiy xodimmi?
3. "psychological_type" — Muloqot uslubi qanday (vaqti tigʻiz amaliyotchi, analitik, samimiy yoki ehtiyotkor)?
4. "solvency_level" — Xarid qobiliyati (Premium bormi, qaysi guruhlarda bor, qanday yozmoqda)?
5. "communication_tip" — Sotuvchi u bilan aynan qanday ohangda va qanday uslubda gaplashishi kerak?
6. "recommended_package" — Jon Brandingʼning qaysi xizmati unga eng mos (Brending, Qadoq, Rebrending, Naming)?
7. "key_icebreaker" — Suhbatni samimiy va ishonchli boshlash uchun 1 ta eng zoʻr gap yoki mavzu.

Javobni FAQAT quyidagi JSON formatda ber:
{{
  "business_domain": "<soha>",
  "estimated_role": "<lavozim / LPR maqomi>",
  "psychological_type": "<psixologik portret>",
  "solvency_level": "<Yuqori / Oʻrtacha / Boshlangʻich>",
  "communication_tip": "<muloqot siri va tavsiya>",
  "recommended_package": "<xizmat paketi>",
  "key_icebreaker": "<muz yorar taklif>"
}}

Foydalanuvchi maʼlumotlari:
- Ismi: {name}
- Username: @{username}
- Bio (Profil taʼrifi): {about}
- Telegram Premium: {is_premium}
- Umumiy guruhlar: {common_chats}
- Til kodi: {lang_code}

Oxirgi yozishmalari:
{chat_history}
{links_summary}
"""


class TelegramLeadProfiler:
    """Telegram mijozlarini toʻliq oʻrganuvchi va profillovchi xizmat."""

    def __init__(self, gemini_client: Optional[Any] = None) -> None:
        self._gemini_client = gemini_client

    async def extract_raw_signals(self, client: Any, user_entity: Any) -> TelegramRawSignals:
        """MTProto orqali mijozning barcha ochiq parametrlarini yigʻish."""
        user_id = user_entity.id
        first_name = getattr(user_entity, "first_name", "") or ""
        last_name = getattr(user_entity, "last_name", "") or ""
        username = getattr(user_entity, "username", "") or ""
        phone = getattr(user_entity, "phone", "") or ""
        is_premium = bool(getattr(user_entity, "premium", False))
        is_verified = bool(getattr(user_entity, "verified", False))
        lang_code = getattr(user_entity, "lang_code", "uz") or "uz"

        about = ""
        common_titles = []
        has_business = False
        business_intro = ""

        try:
            full_user = await client(functions.users.GetFullUserRequest(id=user_id))
            full_obj = getattr(full_user, "full_user", None)
            if full_obj:
                about = getattr(full_obj, "about", "") or ""
                has_business = bool(getattr(full_obj, "business_work_hours", None))
                b_intro = getattr(full_obj, "business_intro", None)
                if b_intro:
                    business_intro = f"{getattr(b_intro, 'title', '')}: {getattr(b_intro, 'description', '')}"
        except Exception as exc:
            logger.debug("[PROFILER] GetFullUserRequest cheklovi: %s", exc)

        try:
            common = await client(GetCommonChatsRequest(user_id=user_id, max_id=0, limit=20))
            for chat in getattr(common, "chats", []):
                title = getattr(chat, "title", "")
                if title:
                    common_titles.append(title)
        except Exception as exc:
            logger.debug("[PROFILER] GetCommonChatsRequest cheklovi: %s", exc)

        photo_count = 0
        try:
            photos = await client.get_profile_photos(user_id, limit=5)
            photo_count = len(photos)
        except Exception:
            pass

        return TelegramRawSignals(
            user_id=user_id,
            first_name=first_name,
            last_name=last_name,
            username=username,
            phone=phone,
            about=about,
            is_premium=is_premium,
            is_verified=is_verified,
            lang_code=lang_code,
            photo_count=photo_count,
            common_chats=common_titles,
            has_business_profile=has_business,
            business_intro=business_intro,
        )

    async def analyze_lead(
        self,
        signals: TelegramRawSignals,
        chat_history: str = "",
    ) -> TelegramLeadProfile:
        """Dosye tuzadi va Instagram/FB sahifalar uchun Ad Library havolalarini qoʻshadi."""
        profile = await self._synthesize_profile(signals, chat_history)
        try:
            from src.services.core.marketing.ad_library_links import find_social_page_queries

            profile.ad_library_queries = find_social_page_queries(f"{signals.about}\n{chat_history}")
        except Exception as exc:
            logger.debug("[PROFILER] Ad Library havolalari qoʻshilmadi: %s", exc)
        return profile

    async def _synthesize_profile(
        self,
        signals: TelegramRawSignals,
        chat_history: str = "",
    ) -> TelegramLeadProfile:
        """Yigʻilgan signallarni Gemini 2.5 AI orqali sintez qilib dosye tuzish."""
        full_name = f"{signals.first_name} {signals.last_name}".strip() or "Nomaʼlum mijoz"
        client = self._get_gemini_client()

        if not client:
            return self._fallback_profile(signals, full_name)

        links_summary = ""
        try:
            from src.services.ai.link_analyzer import LinkAnalyzer
            analyzer = LinkAnalyzer()
            combined_text = f"{signals.about}\n{chat_history}"
            analyzed_links = await analyzer.analyze_text_links(combined_text)
            if analyzed_links:
                links_summary = "\n" + analyzer.format_links_summary(analyzed_links)
        except Exception:
            pass

        prompt = _PROFILER_PROMPT.format(
            name=full_name,
            username=signals.username or "yoʻq",
            about=signals.about or "Yoʻq",
            is_premium="HA (Bor)" if signals.is_premium else "YOʻQ",
            common_chats=", ".join(signals.common_chats[:5]) or "Umumiy guruhlar yoʻq",
            lang_code=signals.lang_code,
            chat_history=chat_history[:2500] if chat_history else "Yozishmalar tarixi hozircha qisqa",
            links_summary=links_summary,
        )

        try:
            from google.genai import types
            response, _model = await generate_content_with_fallback(
                client,
                primary_model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
                log_prefix="[TELEGRAM_PROFILER]",
            )
            raw = getattr(response, "text", "") or ""
            return self._parse_profile_json(raw, signals, full_name)
        except Exception as exc:
            logger.error("[PROFILER] AI tahlilda xatolik: %s", exc)
            return self._fallback_profile(signals, full_name)

    def _parse_profile_json(
        self, raw: str, signals: TelegramRawSignals, full_name: str
    ) -> TelegramLeadProfile:
        clean = raw.strip()
        if clean.startswith("```"):
            clean = re.sub(r"^```(?:json)?\s*", "", clean, flags=re.IGNORECASE)
            clean = re.sub(r"\s*```$", "", clean)

        try:
            data = json.loads(clean)
        except Exception:
            return self._fallback_profile(signals, full_name)

        return TelegramLeadProfile(
            user_id=signals.user_id,
            full_name=full_name,
            username=signals.username,
            phone=signals.phone,
            is_premium=signals.is_premium,
            business_domain=str(data.get("business_domain") or "Biznes / Tadbirkorlik"),
            estimated_role=str(data.get("estimated_role") or "LPR / Qaror qabul qiluvchi"),
            psychological_type=str(data.get("psychological_type") or "Amaliyotchi rahbar"),
            solvency_level=str(data.get("solvency_level") or ("Yuqori" if signals.is_premium else "Oʻrtacha")),
            communication_tip=str(data.get("communication_tip") or "Qisqa, aniq va natijaga yoʻnaltirilgan muloqot"),
            recommended_package=str(data.get("recommended_package") or "Kompleks brending"),
            key_icebreaker=str(data.get("key_icebreaker") or "Loyiha maqsadini aniqlash bilan boshlash"),
        )

    def _fallback_profile(self, signals: TelegramRawSignals, full_name: str) -> TelegramLeadProfile:
        solvency = "Yuqori (Enterprise)" if signals.is_premium else "Oʻrtacha (Business)"
        return TelegramLeadProfile(
            user_id=signals.user_id,
            full_name=full_name,
            username=signals.username,
            phone=signals.phone,
            is_premium=signals.is_premium,
            business_domain="Tadbirkorlik / Ishlab chiqarish",
            estimated_role="Qaror qabul qiluvchi (LPR)",
            psychological_type="Amaliyotchi (aniq natijadorlikni yoqtiradi)",
            solvency_level=solvency,
            communication_tip="Ortiqcha gaplarsiz, aniq portfolio keyslari va muddat bilan gaplashing.",
            recommended_package="Brending va Qadoq dizayni",
            key_icebreaker="Siz aytgan loyiha boʻyicha oʻxshash muvaffaqiyatli keysimizni koʻrib chiqdik.",
        )

    def _get_gemini_client(self) -> Optional[Any]:
        if self._gemini_client is not None:
            return self._gemini_client
        try:
            from google import genai
            api_key = settings.GEMINI_API_KEY.get_secret_value().strip()
            if api_key:
                self._gemini_client = genai.Client(api_key=api_key)
                return self._gemini_client
        except Exception as exc:
            logger.warning("[PROFILER] Gemini client xatosi: %s", exc)
        return None

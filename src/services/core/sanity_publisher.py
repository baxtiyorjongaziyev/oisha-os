import asyncio
import datetime
import structlog
import httpx
import json
from typing import Dict, Any, List, Optional
from src.settings import settings

logger = structlog.get_logger()


class SanityPublisher:
    """📰 Avtomatlashtirilgan Case-Study Publisher.

    AmoCRM'da loyiha 'Muvaffaqiyatli yakunlandi' bosqichiga o'tganda:
    1. Oisha loyiha tafsilotlarini oladi
    2. Gemini orqali professional SEO maqola yozadi
    3. Sanity CMS API orqali jonbranding.uz/cases/ ga chop etadi
    """

    def __init__(self):
        self.project_id = settings.SANITY_PROJECT_ID
        self.dataset = settings.SANITY_DATASET
        token = settings.SANITY_TOKEN.get_secret_value() if settings.SANITY_TOKEN else None
        self.token = token
        self.api_version = "2024-04-14"
        self.base_url = f"https://{self.project_id}.api.sanity.io/v{self.api_version}"
        self.cdn_url = f"https://{self.project_id}.apicdn.sanity.io/v{self.api_version}"
        self.enabled = bool(self.project_id and self.token)

    async def publish_case(self, lead_data: Dict[str, Any]) -> bool:
        """AmoCRM lead ma'lumotlaridan case study yaratish va Sanity ga publish."""
        if not self.enabled:
            logger.warning("[SANITY] Sanity not configured, skipping publish")
            return False

        lead_id = lead_data.get("id")
        lead_name = lead_data.get("name", "Nomsiz Loyiha")

        # 1. AI orqali case study matnini yaratish
        case_content = await self._generate_case_content(lead_data)
        if not case_content:
            logger.error("[SANITY] AI case generation failed", lead=lead_name)
            return False

        # 2. Sanity document yaratish
        doc = {
            "_type": "portfolio",
            "title": case_content.get("title", lead_name),
            "slug": {"_type": "slug", "current": self._make_slug(lead_name)},
            "client": case_content.get("client", lead_data.get("contact_name", "")),
            "category": case_content.get("category", "brand-strategy"),
            "tags": case_content.get("tags", ["brending"]),
            "description": case_content.get("description", ""),
            "body": self._build_body_blocks(case_content),
            "results": case_content.get("results", []),
            "publishedAt": datetime.datetime.now().isoformat(),
        }

        success = await self._sanity_upsert(doc)
        if success:
            logger.info("[SANITY] Case published successfully", lead=lead_name, title=doc["title"])
        else:
            logger.error("[SANITY] Failed to publish case", lead=lead_name)
        return success

    async def _generate_case_content(self, lead: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Gemini yordamida case study matnini yaratish."""
        try:
            from src.services.utils.gemini_fallback import generate_content_with_fallback
            from src.services.core.agent_brain import get_genai_client

            client = get_genai_client()
            if not client:
                logger.warning("[SANITY] No genai client available")
                return self._fallback_content(lead)

            from google.genai import types

            prompt = (
                "Sen professional copywritersan. Jon Branding agentligi uchun portfolio case study yoz.\n\n"
                f"Lead ma'lumotlari:\n"
                f"- Nomi: {lead.get('name', 'N/A')}\n"
                f"- Mijoz: {lead.get('contact_name', lead.get('name', 'N/A'))}\n"
                f"- Narx: {lead.get('price', 0)} so'm\n"
                f"- Status: {lead.get('status_name', 'Yakunlangan')}\n\n"
                "Quyidagi JSON formatda faqat valid JSON qaytar (boshqa matn yo'q):\n"
                "{\n"
                '  "title": "Case study sarlavhasi (30-50 belgi)",\n'
                '  "client": "Mijoz nomi",\n'
                '  "category": "brand-strategy|logo-design|brandbook|corporate-style|packaging|naming",\n'
                '  "description": "Qisqa tavsif (1-2 gap)",\n'
                '  "tags": ["brending", "logotip"],\n'
                '  "challenge": "Muammo tavsifi (2-3 gap)",\n'
                '  "solution": "Yechim tavsifi (3-5 gap)",\n'
                '  "results": [{"metric": "Ko\'rsatkich", "value": "Qiymat"}]\n'
                "}"
            )

            response, _ = await generate_content_with_fallback(
                client,
                primary_model=settings.GEMINI_CALL_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.3,
                ),
                log_prefix="[SANITY]",
            )
            raw = (response.text or "").strip()
            raw = raw.replace("```json", "").replace("```", "").strip()
            return json.loads(raw)
        except Exception as e:
            logger.error("[SANITY] AI content generation error", error=str(e))
            return self._fallback_content(lead)

    def _fallback_content(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """AI ishlamasa, oddiy kontent."""
        name = lead.get("name", "Loyiha")
        return {
            "title": f"Jon Branding: {name}",
            "client": lead.get("contact_name", "Mijoz"),
            "category": "brand-strategy",
            "description": f"{name} loyihasi uchun Jon Branding tomonidan professional brending xizmatlari ko'rsatildi.",
            "tags": ["brending"],
            "challenge": "Mijozning brendini yangi bosqichga olib chiqish vazifasi qo'yilgan edi.",
            "solution": "Jon Branding jamoasi tomonidan to'liq brend-strategiya ishlab chiqildi.",
            "results": [{"metric": "Loyiha qiymati", "value": f"{lead.get('price', 0):,} so'm"}],
        }

    def _build_body_blocks(self, content: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Sanity Portable Text formatida body yaratish."""
        blocks = []
        for section, text in [("Muammo", content.get("challenge", "")),
                              ("Yechim", content.get("solution", ""))]:
            if not text:
                continue
            blocks.append({
                "_type": "block",
                "style": "h2",
                "children": [{"_type": "span", "text": section}],
            })
            blocks.append({
                "_type": "block",
                "style": "normal",
                "children": [{"_type": "span", "text": text}],
            })
        return blocks

    async def _sanity_upsert(self, doc: Dict[str, Any]) -> bool:
        """Sanity CMS ga document yaratish yoki yangilash."""
        if not self.enabled:
            return False
        url = f"{self.base_url}/data/mutate/{self.dataset}"
        mutations = {"mutations": [{"createOrReplace": doc}]}
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    url,
                    json=mutations,
                    headers={
                        "Authorization": f"Bearer {self.token}",
                        "Content-Type": "application/json",
                    },
                )
                if resp.status_code == 200:
                    return True
                logger.warning("[SANITY] API error", status=resp.status_code, body=resp.text)
                return False
        except Exception as e:
            logger.error("[SANITY] API request failed", error=str(e))
            return False

    def _make_slug(self, text: str) -> str:
        """URL slug yaratish."""
        import re
        text = text.lower().strip()
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[\s_]+", "-", text)
        text = re.sub(r"-+", "-", text)
        return text[:80]
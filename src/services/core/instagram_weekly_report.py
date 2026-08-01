"""Weekly Instagram performance report based on Meta Graph API data."""
from __future__ import annotations

import html
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from src.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class InstagramPostInsight:
    media_id: str
    caption: str
    media_type: str
    permalink: str
    timestamp: str
    likes: int
    comments: int
    reach: int
    plays: int
    saves: int
    shares: int
    total_interactions: int
    lead_score: int
    premium_score: int
    lead_reasons: list[str]

    @property
    def headline(self) -> str:
        text = " ".join(self.caption.split())
        return text[:90] + ("..." if len(text) > 90 else "")


class InstagramWeeklyReportAgent:
    """Fetches Instagram insights, stores optional snapshots, and writes a report."""

    GRAPH_BASE = "https://graph.facebook.com/v19.0"

    def __init__(self, settings_obj: Any = settings):
        self.settings = settings_obj

    async def run(self) -> dict[str, Any]:
        posts = await self.fetch_weekly_posts()
        report = await self.build_report(posts)
        await self.store_airtable_report(posts, report)
        return {"posts": posts, "report": report}

    def credential_status(self) -> dict[str, bool]:
        token_obj = getattr(self.settings, "META_PAGE_ACCESS_TOKEN", None)
        access_token = token_obj.get_secret_value() if token_obj else ""
        return {
            "META_INSTAGRAM_USER_ID": bool(self._instagram_user_id()),
            "META_PAGE_ACCESS_TOKEN": bool(access_token.strip()),
        }

    def _instagram_user_id(self) -> str | None:
        return (
            getattr(self.settings, "META_INSTAGRAM_USER_ID", None)
            or getattr(self.settings, "META_INSTAGRAM_ACCOUNT_ID", None)
        )

    async def fetch_weekly_posts(self, days: int = 7) -> list[InstagramPostInsight]:
        ig_user_id = self._instagram_user_id()
        token_obj = getattr(self.settings, "META_PAGE_ACCESS_TOKEN", None)
        access_token = token_obj.get_secret_value() if token_obj else ""
        if not ig_user_id or not access_token:
            missing = [name for name, ok in self.credential_status().items() if not ok]
            logger.warning("[IG-WEEKLY] Missing config: %s", ", ".join(missing))
            return []

        until_dt = datetime.now(timezone.utc)
        since_dt = until_dt - timedelta(days=days)
        media = await self._get_json(
            f"{self.GRAPH_BASE}/{ig_user_id}/media",
            {
                "fields": "id,caption,media_type,media_product_type,permalink,timestamp,like_count,comments_count",
                "since": int(since_dt.timestamp()),
                "until": int(until_dt.timestamp()),
                "limit": 50,
                "access_token": access_token,
            },
        )

        posts: list[InstagramPostInsight] = []
        for item in media.get("data", []):
            if not isinstance(item, dict) or not item.get("id"):
                continue
            insights = await self._fetch_media_insights(item["id"], access_token)
            posts.append(self._normalize_post(item, insights))
        return posts

    async def _fetch_media_insights(self, media_id: str, access_token: str) -> dict[str, int]:
        metric_sets = (
            "reach,plays,saved,shares,total_interactions",
            "reach,saved,shares,total_interactions",
            "impressions,reach,engagement,saved",
        )
        for metrics in metric_sets:
            try:
                data = await self._get_json(
                    f"{self.GRAPH_BASE}/{media_id}/insights",
                    {"metric": metrics, "access_token": access_token},
                )
            except Exception as exc:
                logger.debug("[IG-WEEKLY] insight metric set failed: %s", exc)
                continue
            values: dict[str, int] = {}
            for row in data.get("data", []):
                name = row.get("name")
                raw_value = (row.get("values") or [{}])[0].get("value", 0)
                try:
                    values[name] = int(raw_value or 0)
                except (TypeError, ValueError):
                    values[name] = 0
            if values:
                return values
        return {}

    async def _get_json(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()

    def _normalize_post(self, item: dict[str, Any], insights: dict[str, int]) -> InstagramPostInsight:
        caption = item.get("caption") or ""
        likes = int(item.get("like_count") or 0)
        comments = int(item.get("comments_count") or 0)
        reach = insights.get("reach", insights.get("impressions", 0))
        plays = insights.get("plays", 0)
        saves = insights.get("saved", 0)
        shares = insights.get("shares", 0)
        total_interactions = insights.get("total_interactions", insights.get("engagement", 0))
        lead_score, reasons = self._lead_score(caption, comments, saves, shares)
        premium_score = self._premium_score(caption, saves, shares, total_interactions)
        return InstagramPostInsight(
            media_id=item["id"],
            caption=caption,
            media_type=item.get("media_product_type") or item.get("media_type") or "UNKNOWN",
            permalink=item.get("permalink") or "",
            timestamp=item.get("timestamp") or "",
            likes=likes,
            comments=comments,
            reach=reach,
            plays=plays,
            saves=saves,
            shares=shares,
            total_interactions=total_interactions,
            lead_score=lead_score,
            premium_score=premium_score,
            lead_reasons=reasons,
        )

    def _lead_score(self, caption: str, comments: int, saves: int, shares: int) -> tuple[int, list[str]]:
        text = caption.lower()
        reasons: list[str] = []
        score = min(comments * 4 + saves * 3 + shares * 5, 70)
        keyword_groups = {
            "xizmat/brief": ["brief", "audit", "konsultatsiya", "narx", "price", "branding", "brending"],
            "case/ishonch": ["case", "natija", "mijoz", "portfolio", "before", "after"],
            "premium til": ["premium", "strategiya", "pozitsionirovka", "servis", "jarayon"],
        }
        for reason, keywords in keyword_groups.items():
            if any(keyword in text for keyword in keywords):
                score += 10
                reasons.append(reason)
        return min(score, 100), reasons

    def _premium_score(self, caption: str, saves: int, shares: int, total_interactions: int) -> int:
        text = caption.lower()
        score = min(saves * 5 + shares * 7 + total_interactions, 60)
        premium_terms = [
            "case",
            "jarayon",
            "strategiya",
            "servis",
            "mijoz",
            "natija",
            "tizim",
            "pozitsionirovka",
        ]
        score += sum(8 for term in premium_terms if term in text)
        vanity_terms = ["mashina", "soat", "ofis", "luxury", "qimmat"]
        score -= sum(10 for term in vanity_terms if term in text)
        return max(0, min(score, 100))

    async def build_report(self, posts: list[InstagramPostInsight]) -> str:
        if not posts:
            missing = [name for name, ok in self.credential_status().items() if not ok]
            missing_text = ", ".join(missing) if missing else "Meta insights bo‘sh yoki permission yetarli emas"
            return (
                "📊 <b>Instagram haftalik hisobot</b>\n\n"
                f"Real Meta insights topilmadi. Tekshiruv: {html.escape(missing_text)}."
            )
        ai_report = await self._build_ai_report(posts)
        return ai_report or self._build_deterministic_report(posts)

    async def _build_ai_report(self, posts: list[InstagramPostInsight]) -> str | None:
        token_obj = getattr(self.settings, "OPENAI_API_KEY", None)
        api_key = token_obj.get_secret_value() if token_obj else ""
        if not api_key:
            return None
        try:
            from openai import AsyncOpenAI
        except Exception:
            logger.error("Exception handled in %s", __name__, exc_info=True)
            return None

        rows = []
        for post in posts:
            rows.append(
                {
                    "caption": post.headline,
                    "type": post.media_type,
                    "reach": post.reach,
                    "likes": post.likes,
                    "comments": post.comments,
                    "saves": post.saves,
                    "shares": post.shares,
                    "total_interactions": post.total_interactions,
                    "lead_score": post.lead_score,
                    "premium_score": post.premium_score,
                    "permalink": post.permalink,
                }
            )
        prompt = (
            "Faqat quyidagi real Instagram Meta insights asosida qisqa Uzbek HTML Telegram hisobot yoz. "
            "O'ylab topma. Premium ko'rinish = qimmat mashina/ofis/soat emas; qimmat tafakkur, kuchli case, "
            "jamoa jarayoni, yirik mijozlar tili va professional servis ko'rinishi. "
            "Bo'limlar: yaxshi ishlagan kontent, leadga yaqin post, ko'paytirish kerak mavzular, "
            "premium perception bermayotgan format, keyingi hafta 3 tavsiya.\n\n"
            f"DATA: {rows}"
        )
        try:
            client = AsyncOpenAI(api_key=api_key)
            response = await client.chat.completions.create(
                model=getattr(self.settings, "OPENAI_TEXT_MODEL", "gpt-4o-mini"),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=700,
            )
            content = response.choices[0].message.content if response.choices else None
            return self._safe_telegram_html(content.strip()) if content else None
        except Exception as exc:
            logger.warning("[IG-WEEKLY] OpenAI report failed: %s", exc)
            return None

    def _safe_telegram_html(self, text: str, limit: int = 3500) -> str:
        escaped = html.escape(text[:limit])
        for tag in ("b", "i", "u", "code", "pre"):
            escaped = escaped.replace(f"&lt;{tag}&gt;", f"<{tag}>")
            escaped = escaped.replace(f"&lt;/{tag}&gt;", f"</{tag}>")
        escaped = re.sub(r"&lt;br\\s*/?&gt;", "\n", escaped, flags=re.IGNORECASE)
        return escaped

    def _build_deterministic_report(self, posts: list[InstagramPostInsight]) -> str:
        top = sorted(posts, key=lambda p: (p.total_interactions, p.saves, p.comments), reverse=True)[:3]
        lead = max(posts, key=lambda p: p.lead_score)
        weak_premium = sorted(posts, key=lambda p: (p.premium_score, -p.reach))[:2]
        themes = self._theme_suggestions(posts)
        lines = [
            "📊 <b>Instagram haftalik hisobot</b>",
            "",
            "🔥 <b>Yaxshi ishlagan kontent:</b>",
        ]
        for post in top:
            lines.append(
                f"• {html.escape(post.headline or post.media_type)} — reach {post.reach}, "
                f"save {post.saves}, share {post.shares}, comment {post.comments}"
            )
        lines.extend(
            [
                "",
                "🎯 <b>Leadga yaqin post:</b>",
                f"• {html.escape(lead.headline or lead.media_type)} — lead score {lead.lead_score}/100",
                f"• Sabab: {html.escape(', '.join(lead.lead_reasons) or 'engagement signallari')}",
                "",
                "📈 <b>Ko‘paytirish kerak mavzular:</b>",
                f"• {html.escape('; '.join(themes))}",
                "",
                "⚠️ <b>Premium perception bermayotgan formatlar:</b>",
            ]
        )
        for post in weak_premium:
            lines.append(f"• {html.escape(post.headline or post.media_type)} — premium score {post.premium_score}/100")
        lines.extend(
            [
                "",
                "🧠 <b>105-savol tuzatishi:</b>",
                "Premium ko‘rinishning asosi qimmat buyum emas: qimmat tafakkur + kuchli case + jamoa jarayoni + yirik mijozlar tili + professional servis.",
            ]
        )
        return "\n".join(lines)

    def _theme_suggestions(self, posts: list[InstagramPostInsight]) -> list[str]:
        joined = " ".join(post.caption.lower() for post in posts)
        suggestions = []
        for label, terms in {
            "case va natijalar": ["case", "natija", "before", "after"],
            "jamoa jarayoni": ["jarayon", "team", "jamoa", "process"],
            "strategik fikrlash": ["strategiya", "pozitsionirovka", "brend", "branding"],
            "servis va mijoz tajribasi": ["servis", "mijoz", "support", "tajriba"],
        }.items():
            if any(term in joined for term in terms):
                suggestions.append(label)
        return suggestions[:3] or ["case", "jamoa jarayoni", "professional servis"]

    async def store_airtable_report(self, posts: list[InstagramPostInsight], report: str) -> None:
        base_id = getattr(self.settings, "AIRTABLE_BASE_ID", None)
        table = getattr(self.settings, "INSTAGRAM_REPORT_AIRTABLE_TABLE", None)
        if not base_id or not table:
            return
        try:
            from src.services.core.airtable_client import AirtableClient

            records = [
                {
                    "fields": {
                        "media_id": post.media_id,
                        "caption": post.caption[:1000],
                        "media_type": post.media_type,
                        "permalink": post.permalink,
                        "reach": post.reach,
                        "likes": post.likes,
                        "comments": post.comments,
                        "saves": post.saves,
                        "shares": post.shares,
                        "lead_score": post.lead_score,
                        "premium_score": post.premium_score,
                    }
                }
                for post in posts[:10]
            ]
            if records:
                await AirtableClient().create_records(base_id, table, records)
        except Exception as exc:
            logger.warning("[IG-WEEKLY] Airtable store skipped: %s", exc)

"""
Haftalik Meta app health-check.

Meta Social Technologies MCP faqat interaktiv OAuth bilan ishlaydi, shuning uchun
Oracle'dagi runtime xuddi shu signallarni to'g'ridan-to'g'ri Graph API'dan oladi:
token amal qilishi va ruxsatlari, rate limit, Page webhook obunasi va API versiya.
Faqat o'qish — hech narsa o'zgartirilmaydi. Token log yoki hisobotga chiqmaydi.
"""
from __future__ import annotations

import html
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

import httpx

from src.services.core.instagram.graph_client import InstagramGraphClient

logger = logging.getLogger(__name__)

OK, WARN, FAIL = "ok", "warn", "fail"
_ICONS = {OK: "✅", WARN: "⚠️", FAIL: "❌"}

REQUIRED_SCOPES = (
    "instagram_basic",
    "instagram_manage_messages",
    "instagram_manage_comments",
)
USAGE_WARN_PCT = 75
TOKEN_EXPIRY_WARN_DAYS = 14

# (status, json_body, headers)
GraphResponse = tuple[int, dict[str, Any], dict[str, str]]
HttpGet = Callable[[str, dict[str, Any], str], Awaitable[GraphResponse]]


@dataclass
class HealthFinding:
    level: str
    title: str
    detail: str


async def _default_http_get(url: str, params: dict[str, Any], token: str) -> GraphResponse:
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(
            url, params=params, headers={"Authorization": f"Bearer {token}"}
        )
    try:
        body = response.json()
    except ValueError:
        body = {}
    headers = {k.lower(): v for k, v in response.headers.items()}
    return response.status_code, body if isinstance(body, dict) else {}, headers


def _graph_error(body: dict[str, Any]) -> str:
    err = body.get("error") or {}
    return str(err.get("message") or "noma'lum xato")[:160]


class MetaHealthCheck:
    """Meta app holatini o'qib, `HealthFinding` ro'yxatini qaytaradi."""

    def __init__(self, client: InstagramGraphClient | None = None, http_get: HttpGet | None = None):
        self.client = client or InstagramGraphClient()
        self._http_get = http_get or _default_http_get

    @property
    def configured(self) -> bool:
        return bool(self.client.access_token)

    def _url(self, path: str) -> str:
        return f"https://graph.facebook.com/{self.client.api_version}/{path.lstrip('/')}"

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> GraphResponse | None:
        try:
            return await self._http_get(self._url(path), params or {}, self.client.access_token)
        except httpx.HTTPError as exc:
            logger.warning("[META-HEALTH] %s so'rovi yiqildi: %s", path.split("?")[0], type(exc).__name__)
            return None

    async def run(self) -> list[HealthFinding]:
        if not self.configured:
            return [HealthFinding(FAIL, "Sozlama", "META_PAGE_ACCESS_TOKEN berilmagan")]
        findings: list[HealthFinding] = []
        token_data = await self._check_token(findings)
        await self._check_page_webhook(findings, str(token_data.get("app_id") or ""))
        return findings

    async def _check_token(self, findings: list[HealthFinding]) -> dict[str, Any]:
        res = await self._get("debug_token", {"input_token": self.client.access_token})
        if res is None:
            findings.append(HealthFinding(FAIL, "Graph API", "Meta serveriga ulanib bo'lmadi"))
            return {}
        status, body, headers = res
        findings.extend(self._usage_findings(headers))
        findings.extend(self._version_findings(headers))
        data = body.get("data") or {}
        if status != 200 or not data:
            findings.append(HealthFinding(FAIL, "Token", f"Tekshirib bo'lmadi: {_graph_error(body)}"))
            return {}
        findings.extend(self._token_findings(data))
        return data

    def _token_findings(self, data: dict[str, Any]) -> list[HealthFinding]:
        if not data.get("is_valid"):
            msg = (data.get("error") or {}).get("message") or "token yaroqsiz"
            return [HealthFinding(FAIL, "Token", f"Yaroqsiz: {str(msg)[:160]}")]
        out = [self._expiry_finding(data)]
        scopes = set(data.get("scopes") or [])
        missing = [s for s in REQUIRED_SCOPES if s not in scopes]
        if missing:
            out.append(HealthFinding(FAIL, "Ruxsatlar", "Yetishmaydi: " + ", ".join(missing)))
        else:
            out.append(HealthFinding(OK, "Ruxsatlar", f"DM va comment ruxsatlari bor ({len(scopes)} ta scope)"))
        return out

    @staticmethod
    def _expiry_finding(data: dict[str, Any], now: datetime | None = None) -> HealthFinding:
        expires_at = int(data.get("expires_at") or 0)
        if expires_at == 0:
            return HealthFinding(OK, "Token", "Amal qiladi, muddatsiz")
        now = now or datetime.now(timezone.utc)
        days_left = (datetime.fromtimestamp(expires_at, timezone.utc) - now).days
        if days_left < TOKEN_EXPIRY_WARN_DAYS:
            return HealthFinding(WARN, "Token", f"{max(days_left, 0)} kunda tugaydi — yangilang")
        return HealthFinding(OK, "Token", f"Amal qiladi, {days_left} kun qoldi")

    @staticmethod
    def _usage_findings(headers: dict[str, str]) -> list[HealthFinding]:
        peak = 0
        for key in ("x-app-usage", "x-business-use-case-usage"):
            peak = max(peak, _peak_usage(headers.get(key)))
        if peak >= USAGE_WARN_PCT:
            return [HealthFinding(WARN, "Rate limit", f"Limitning {peak}% ishlatilgan")]
        return [HealthFinding(OK, "Rate limit", f"Eng yuqori yuklama {peak}%")]

    def _version_findings(self, headers: dict[str, str]) -> list[HealthFinding]:
        configured = self.client.api_version
        served = (headers.get("facebook-api-version") or "").strip()
        if served and served != configured:
            return [HealthFinding(
                WARN, "API versiya",
                f"{configured} so'raldi, Meta {served} bilan javob berdi — "
                f"{configured} eskirgan, META_GRAPH_API_VERSION ni yangilang",
            )]
        return [HealthFinding(OK, "API versiya", f"{configured} ishlayapti")]

    async def _check_page_webhook(self, findings: list[HealthFinding], app_id: str) -> None:
        page_id = self.client.page_id
        if not page_id:
            findings.append(HealthFinding(WARN, "Webhook", "META_PAGE_ID berilmagan — tekshirilmadi"))
            return
        res = await self._get(f"{page_id}/subscribed_apps")
        if res is None or res[0] != 200:
            detail = _graph_error(res[1]) if res else "ulanib bo'lmadi"
            findings.append(HealthFinding(FAIL, "Webhook", f"Obunani o'qib bo'lmadi: {detail}"))
            return
        apps = [a for a in res[1].get("data") or [] if isinstance(a, dict)]
        ours = next((a for a in apps if not app_id or str(a.get("id")) == app_id), None)
        if ours is None:
            findings.append(HealthFinding(FAIL, "Webhook", "Oisha app'i Page'ga obuna emas — DM kelmaydi"))
            return
        fields = ours.get("subscribed_fields") or []
        if not fields:
            findings.append(HealthFinding(WARN, "Webhook", "Obuna bor, lekin field'lar bo'sh"))
            return
        findings.append(HealthFinding(OK, "Webhook", "Field'lar: " + ", ".join(map(str, fields[:8]))))


def _peak_usage(raw: str | None) -> int:
    """X-App-Usage / X-Business-Use-Case-Usage header'idan eng katta foizni oladi."""
    if not raw:
        return 0
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return 0
    rows: list[dict[str, Any]] = []
    if isinstance(parsed, dict) and "call_count" in parsed:
        rows = [parsed]
    elif isinstance(parsed, dict):
        for value in parsed.values():
            if isinstance(value, list):
                rows.extend(r for r in value if isinstance(r, dict))
    peak = 0
    for row in rows:
        for key in ("call_count", "total_cputime", "total_time"):
            try:
                peak = max(peak, int(row.get(key) or 0))
            except (TypeError, ValueError):
                continue
    return peak


def format_report(findings: list[HealthFinding], now: datetime | None = None) -> str:
    """Telegram uchun HTML hisobot."""
    worst = FAIL if any(f.level == FAIL for f in findings) else (
        WARN if any(f.level == WARN for f in findings) else OK
    )
    headline = {OK: "hammasi joyida", WARN: "e'tibor kerak", FAIL: "muammo bor"}[worst]
    date = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%d")
    lines = [f"<b>{_ICONS[worst]} Meta app health-check — {headline}</b>", f"<i>{date}</i>", ""]
    for f in findings:
        lines.append(f"{_ICONS[f.level]} <b>{html.escape(f.title)}:</b> {html.escape(f.detail)}")
    if worst != OK:
        lines += ["", "Batafsil: Claude Code'da Meta Social Technologies MCP orqali tekshiring."]
    return "\n".join(lines)

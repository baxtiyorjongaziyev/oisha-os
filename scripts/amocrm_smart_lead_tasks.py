"""Create amoCRM tasks from real call + Telegram conversation context.

This is the corrective pipeline for the CRM cleanup task coverage pass. It does
not create generic "call this lead" tasks. For every lead it can inspect, it
builds a context pack from:

- amoCRM notes and existing call analysis transcripts;
- raw audio URLs / audio attachments when available;
- local Telegram DB history by phone;
- optional Telegram userbot history by phone.

Then it writes one contextual note and one contextual `Oisha smart:` task, and
closes the generic `Oisha audit:` placeholder task for that lead.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import inspect
import json
import os
import re
import sqlite3
import sys
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.services.core.amocrm_lead_enrichment import normalize_phone
from src.services.core.amocrm_sync import AmoCRMSync
from src.services.core.call_analyzer import CallAnalyzer
from src.settings import settings


STATUS_WON = 142
STATUS_LOST = 143

SMART_TASK_PREFIX = "Oisha smart:"
SMART_NOTE_MARKER = "[Oisha Smart Lead Analysis]"
GENERIC_TASK_PREFIX = "Oisha audit:"

AUDIO_EXTENSIONS = (".mp3", ".mp4", ".m4a", ".ogg", ".wav", ".flac", ".aac", ".opus", ".webm", ".amr")

PHONE_RE = re.compile(r"(?:\+?998[\s\-()]*)?\d{2}[\s\-()]*\d{3}[\s\-()]*\d{2}[\s\-()]*\d{2}")
URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)


async def maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def clip(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 20)].rstrip() + "\n...[qisqartirildi]"


def extract_json(raw: str) -> dict[str, Any]:
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            return json.loads(raw[start : end + 1])
        raise


def extract_phone_from_text(text: str) -> str:
    match = PHONE_RE.search(text or "")
    return normalize_phone(match.group(0)) if match else ""


def text_from_note(note: dict[str, Any]) -> str:
    params = note.get("params") or {}
    if isinstance(params, dict):
        if params.get("text"):
            return str(params.get("text") or "")
        if params.get("message"):
            return str(params.get("message") or "")
        return " ".join(str(v) for v in params.values() if isinstance(v, (str, int, float)))
    return ""


def parse_ai_call_note(text: str) -> dict[str, Any] | None:
    if "[AI_CALL_ANALYSIS]" not in (text or ""):
        return None

    def field(label: str, until: Iterable[str] = ()) -> str:
        labels = "|".join(re.escape(item) for item in until)
        if labels:
            pattern = rf"{re.escape(label)}:\s*(.*?)(?=\n(?:{labels}):|\Z)"
        else:
            pattern = rf"{re.escape(label)}:\s*(.*?)(?=\n[A-ZА-ЯЁO'`a-zA-Zа-яёЎҚҒҲІЁ ,()]+:|\Z)"
        match = re.search(pattern, text, flags=re.DOTALL)
        return (match.group(1).strip() if match else "")

    call_id = field("Call ID", ["Sdelka", "Sana", "Telefon"])
    phone = field("Telefon", ["Davomiylik", "Toifa", "Kayfiyat"])
    duration = field("Davomiylik", ["Toifa", "Kayfiyat", "Suhbat xulosasi"])
    category = field("Toifa", ["Kayfiyat", "Suhbat xulosasi"])
    mood = field("Kayfiyat", ["Suhbat xulosasi", "Keyingi qadamlar"])
    summary = field("Suhbat xulosasi", ["Keyingi qadamlar", "Transkript (Google STT)", "Tozalangan UZ parcha"])
    next_steps = field("Keyingi qadamlar", ["Transkript (Google STT)", "Tozalangan UZ parcha"])
    transcript = field("Transkript (Google STT)", ["Tozalangan UZ parcha"])
    clean_snippet = field("Tozalangan UZ parcha")

    return {
        "source": "amocrm_ai_call_note",
        "call_id": call_id,
        "phone": normalize_phone(phone),
        "duration": duration,
        "category": category,
        "mood": mood,
        "summary": summary,
        "next_steps": next_steps,
        "transcript": transcript,
        "clean_snippet": clean_snippet,
    }


@dataclass
class LeadContext:
    lead: dict[str, Any]
    phone: str = ""
    notes: list[dict[str, Any]] = field(default_factory=list)
    call_analyses: list[dict[str, Any]] = field(default_factory=list)
    audio_transcripts: list[dict[str, Any]] = field(default_factory=list)
    telegram_messages: list[dict[str, Any]] = field(default_factory=list)
    warning: str = ""
    open_tasks: list[dict[str, Any]] = field(default_factory=list)

    @property
    def lead_id(self) -> int:
        return int(self.lead["id"])

    def has_context(self) -> bool:
        telegram_chars = sum(len(str(msg.get("text") or "")) for msg in self.telegram_messages)
        return bool(self.call_analyses or self.audio_transcripts or telegram_chars >= 250)


@dataclass
class SmartDecision:
    category: str
    qualification: str
    confidence: float
    summary: str
    next_task_text: str
    due_in_hours: int
    tags: list[str]
    evidence: list[str]
    should_create_task: bool = True


class SmartLeadTaskPipeline:
    def __init__(
        self,
        *,
        dry_run: bool,
        limit: int,
        only_with_context: bool,
        use_userbot: bool,
        force: bool,
    ):
        self.dry_run = dry_run
        self.limit = max(1, int(limit or 20))
        self.only_with_context = only_with_context
        self.use_userbot = use_userbot
        self.force = force
        self.tz = ZoneInfo(settings.APP_TIMEZONE or "Asia/Tashkent")
        self.now = datetime.now(self.tz)
        self.stamp = self.now.strftime("%Y%m%d_%H%M%S")
        self.report_dir = Path("data/reports")
        self.report_dir.mkdir(parents=True, exist_ok=True)

        self.db = None
        self.amocrm = AmoCRMSync(
            subdomain=settings.AMOCRM_SUBDOMAIN,
            client_id=settings.AMOCRM_CLIENT_ID,
            client_secret=(
                settings.AMOCRM_CLIENT_SECRET.get_secret_value()
                if settings.AMOCRM_CLIENT_SECRET
                else ""
            ),
            redirect_url=settings.AMOCRM_REDIRECT_URL,
        )
        self.call_analyzer: CallAnalyzer | None = None
        self.user_client: Any = None
        self.genai_client: Any = None
        self.actions: list[dict[str, Any]] = []
        self.errors: list[dict[str, Any]] = []

    async def setup(self) -> None:
        self.call_analyzer = CallAnalyzer(amocrm=self.amocrm, db=self.db)
        self.genai_client = getattr(self.call_analyzer, "genai_client", None)
        if self.use_userbot:
            self.user_client = await self.build_userbot_client()

    async def close(self) -> None:
        if self.user_client:
            try:
                await self.user_client.disconnect()
            except Exception:
                pass
        try:
            if self.db:
                await self.db.close()
        except Exception:
            pass

    async def build_userbot_client(self) -> Any:
        try:
            from telethon import TelegramClient
            from telethon.sessions import StringSession
        except Exception as exc:
            self.record_error("userbot_import", None, str(exc))
            return None

        if not settings.API_ID or not settings.API_HASH:
            self.record_error("userbot_config", None, "API_ID/API_HASH not configured")
            return None

        session_string = ""
        try:
            session_string = (
                settings.USERBOT_SESSION_STRING.get_secret_value()
                if settings.USERBOT_SESSION_STRING
                else ""
            )
        except Exception:
            session_string = ""

        try:
            if session_string:
                client = TelegramClient(
                    StringSession(session_string),
                    api_id=settings.API_ID,
                    api_hash=settings.API_HASH,
                )
            else:
                session_name = "userbot_session"
                if not Path("userbot_session.session").exists() and Path("data/userbot_session.session").exists():
                    session_name = str(Path("data/userbot_session").resolve())
                client = TelegramClient(session_name, api_id=settings.API_ID, api_hash=settings.API_HASH)
            await client.connect()
            if not await client.is_user_authorized():
                await client.disconnect()
                self.record_error("userbot_auth", None, "userbot session is not authorized")
                return None
            return client
        except Exception as exc:
            self.record_error("userbot_connect", None, str(exc))
            return None

    def record(self, action: str, lead_id: int | None = None, **metadata: Any) -> None:
        self.actions.append({"action": action, "lead_id": lead_id, **metadata})

    def record_error(self, action: str, lead_id: int | None, error: str) -> None:
        self.errors.append({"action": action, "lead_id": lead_id, "error": error[:1000]})

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_payload: Any = None,
    ) -> requests.Response:
        response = requests.request(
            method,
            f"{self.amocrm.base_url}{path}",
            headers=self.amocrm._get_headers(),
            params=params,
            json=json_payload,
            timeout=45,
        )
        if response.status_code == 401 and self.amocrm.refresh_token():
            response = requests.request(
                method,
                f"{self.amocrm.base_url}{path}",
                headers=self.amocrm._get_headers(),
                params=params,
                json=json_payload,
                timeout=45,
            )
        return response

    def fetch_paginated(
        self,
        path: str,
        item_key: str,
        *,
        params: dict[str, Any] | None = None,
        max_pages: int = 30,
    ) -> list[dict[str, Any]]:
        query = dict(params or {})
        query.setdefault("limit", 250)
        items: list[dict[str, Any]] = []
        for page in range(1, max_pages + 1):
            query["page"] = page
            response = self.request("GET", path, params=query)
            response.raise_for_status()
            payload = response.json() if response.text else {}
            batch = payload.get("_embedded", {}).get(item_key, []) or []
            items.extend(batch)
            if not batch or "next" not in (payload.get("_links") or {}):
                break
        return items

    def fetch_open_tasks(self) -> dict[int, list[dict[str, Any]]]:
        tasks = self.fetch_paginated(
            "/api/v4/tasks",
            "tasks",
            params={"filter[is_completed]": 0},
            max_pages=80,
        )
        by_lead: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for task in tasks:
            if task.get("entity_type") == "leads" and task.get("entity_id"):
                by_lead[int(task["entity_id"])].append(task)
        return by_lead

    def fetch_candidate_leads(self) -> list[dict[str, Any]]:
        leads = self.fetch_paginated(
            "/api/v4/leads",
            "leads",
            params={"with": "contacts"},
            max_pages=120,
        )
        active = [lead for lead in leads if int(lead.get("status_id") or 0) not in {STATUS_WON, STATUS_LOST}]

        def score(lead: dict[str, Any]) -> tuple[int, int]:
            name = str(lead.get("name") or "")
            tags = {str(t.get("name") or "") for t in lead.get("_embedded", {}).get("tags", []) or []}
            priority = 0
            if "OISHA_REACTIVATE" in tags:
                priority += 3
            if "OISHA_REVIVE_24H" in tags or "OISHA_MEETING_REVIEW" in tags:
                priority += 2
            if "Звонок" in name or "+" in name:
                priority += 2
            return (priority, int(lead.get("updated_at") or 0))

        return sorted(active, key=score, reverse=True)

    def fetch_lead(self, lead_id: int) -> dict[str, Any] | None:
        response = self.request("GET", f"/api/v4/leads/{lead_id}", params={"with": "contacts"})
        if response.status_code == 200:
            return response.json()
        self.record_error("fetch_lead", lead_id, f"HTTP {response.status_code}: {response.text[:400]}")
        return None

    async def build_context(
        self,
        lead: dict[str, Any],
        open_tasks: list[dict[str, Any]],
    ) -> LeadContext:
        lead_id = int(lead["id"])
        context = LeadContext(lead=lead, open_tasks=open_tasks)
        context.phone = await self.extract_phone(lead)

        response = self.request("GET", f"/api/v4/leads/{lead_id}/notes", params={"limit": 100})
        if response.status_code == 200:
            context.notes = response.json().get("_embedded", {}).get("notes", []) or []
        elif response.status_code == 204:
            context.notes = []
        else:
            self.record_error("fetch_notes", lead_id, f"HTTP {response.status_code}: {response.text[:300]}")

        for note in context.notes:
            text = text_from_note(note)
            lowered = text.lower()
            if "noto'g'ri" in lowered and ("transkript" in lowered or "transkrit" in lowered or "speech-to-text" in lowered):
                context.warning = "Oldingi STT/transkript bo'yicha xatolik ogohlantirishi bor."
            parsed = parse_ai_call_note(text)
            if parsed:
                context.call_analyses.append(parsed)
                if parsed.get("phone") and not context.phone:
                    context.phone = parsed["phone"]

        await self.transcribe_raw_audio_if_available(context)
        context.telegram_messages = await self.collect_telegram_context(context.phone)
        return context

    async def extract_phone(self, lead: dict[str, Any]) -> str:
        phone = extract_phone_from_text(str(lead.get("name") or ""))
        if phone:
            return phone
        try:
            raw = await asyncio.to_thread(self.amocrm.get_lead_phone, int(lead["id"]))
            return normalize_phone(raw)
        except Exception:
            return ""

    async def transcribe_raw_audio_if_available(self, context: LeadContext) -> None:
        if not self.call_analyzer:
            return

        for note in context.notes[:50]:
            params = note.get("params") or {}
            audio_url = self.call_analyzer._find_audio_url(params)
            audio_bytes: bytes | None = None
            mime_type = ""
            source = ""

            if audio_url:
                fetched = await self.call_analyzer._fetch_audio_bytes(audio_url)
                if fetched:
                    audio_bytes, mime_type = fetched
                    source = audio_url
            elif note.get("note_type") == "attachment" and isinstance(params, dict):
                file_name = str(params.get("file_name") or params.get("original_name") or "").lower()
                file_uuid = str(params.get("file_uuid") or "")
                if file_uuid and file_name.endswith(AUDIO_EXTENSIONS):
                    data = await asyncio.to_thread(self.amocrm.download_file, file_uuid)
                    if data:
                        audio_bytes = data
                        mime_type = self.call_analyzer._detect_mime(file_name) if hasattr(self.call_analyzer, "_detect_mime") else "audio/mpeg"
                        source = f"file_uuid:{file_uuid}"

            if not audio_bytes:
                continue

            digest = hashlib.sha1(audio_bytes[:4096]).hexdigest()[:12]
            transcript = await self.call_analyzer._transcribe_inline(audio_bytes, mime_type or "audio/mpeg")
            if transcript:
                context.audio_transcripts.append(
                    {
                        "source": source,
                        "digest": digest,
                        "transcript": transcript,
                    }
                )
                self.record("audio_transcribed", context.lead_id, source=source, chars=len(transcript))
                return

    async def collect_telegram_context(self, phone: str) -> list[dict[str, Any]]:
        if not phone:
            return []

        messages: list[dict[str, Any]] = []
        try:
            local_messages = self.collect_local_sqlite_context(phone)
            if local_messages:
                return local_messages[-30:]
        except Exception as exc:
            self.record("telegram_local_db_unavailable", error=str(exc)[:1000])

        if self.db:
            try:
                user = await self.db.get_user_by_phone(phone)
                user_id = int(user["user_id"]) if user and user.get("user_id") else None
                if user_id:
                    history = await self.db.get_recent_messages(user_id, limit=30)
                    for item in history or []:
                        text = ""
                        if item.get("parts"):
                            text = str(item["parts"][0].get("text") or "")
                        else:
                            text = str(item.get("message_text") or item.get("text") or "")
                        if text:
                            messages.append(
                                {
                                    "source": "database",
                                    "role": "Menejer/Oisha" if item.get("role") == "model" else "Mijoz",
                                    "text": clip(text, 900),
                                }
                            )
            except Exception as exc:
                self.record("telegram_db_context_failed", error=str(exc)[:1000])

        if messages or not self.user_client:
            return messages[-30:]

        try:
            entity = await self.resolve_telegram_entity(phone)
            if not entity:
                return []
            fetched = await self.user_client.get_messages(entity, limit=30)
            for msg in reversed(list(fetched or [])):
                text = str(getattr(msg, "message", "") or "").strip()
                if not text:
                    continue
                messages.append(
                    {
                        "source": "userbot",
                        "role": "Menejer" if getattr(msg, "out", False) else "Mijoz",
                        "text": clip(text, 900),
                        "created_at": str(getattr(msg, "date", "") or ""),
                    }
                )
        except Exception as exc:
            self.record_error("telegram_userbot_context", None, str(exc))

        return messages[-30:]

    def collect_local_sqlite_context(self, phone: str) -> list[dict[str, Any]]:
        normalized = normalize_phone(phone)
        short = re.sub(r"\D+", "", normalized)[-9:]
        if not short:
            return []

        db_paths = [
            Path("bot_database.db"),
            Path("data/bot.db"),
            Path("data/bot_database.db"),
        ]

        for db_path in db_paths:
            if not db_path.exists() or db_path.stat().st_size <= 0:
                continue
            try:
                conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
                conn.row_factory = sqlite3.Row
                tables = {
                    row[0]
                    for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
                }
                if "users" not in tables or "message_logs" not in tables:
                    conn.close()
                    continue

                user_row = conn.execute(
                    "SELECT user_id, username, first_name, phone FROM users WHERE phone = ? OR phone LIKE ? LIMIT 1",
                    (normalized, f"%{short}"),
                ).fetchone()
                if not user_row:
                    conn.close()
                    continue

                rows = conn.execute(
                    """
                    SELECT message_text, is_ai_reply, created_at
                    FROM message_logs
                    WHERE user_id = ? AND message_text IS NOT NULL AND message_text != ''
                    ORDER BY created_at DESC
                    LIMIT 30
                    """,
                    (user_row["user_id"],),
                ).fetchall()
                conn.close()

                messages = []
                for row in reversed(rows):
                    text = str(row["message_text"] or "").strip()
                    if not text or text.startswith("ERROR:"):
                        continue
                    messages.append(
                        {
                            "source": str(db_path),
                            "role": "Menejer/Oisha" if row["is_ai_reply"] else "Mijoz",
                            "text": clip(text, 900),
                            "created_at": str(row["created_at"] or ""),
                        }
                    )
                return messages
            except Exception:
                continue

        return []

    async def resolve_telegram_entity(self, phone: str) -> Any:
        if not self.user_client:
            return None
        try:
            return await self.user_client.get_input_entity(phone)
        except Exception:
            pass

        try:
            from telethon import functions, types

            clean_phone = normalize_phone(phone).replace("+", "")
            contact = types.InputPhoneContact(
                client_id=int(time.time() * 1000),
                phone=clean_phone,
                first_name="Oisha Lookup",
                last_name="",
            )
            result = await self.user_client(functions.contacts.ImportContactsRequest(contacts=[contact]))
            users = getattr(result, "users", None) or []
            if not users:
                return None
            return await self.user_client.get_input_entity(users[0])
        except Exception:
            return None

    async def decide(self, context: LeadContext) -> SmartDecision:
        if self.genai_client:
            try:
                return await self.decide_with_gemini(context)
            except Exception as exc:
                self.record("gemini_decision_fallback", context.lead_id, error=str(exc)[:1000])
        return self.fallback_decision(context)

    async def decide_with_gemini(self, context: LeadContext) -> SmartDecision:
        from google.genai import types

        lead = context.lead
        payload = {
            "today": self.now.strftime("%Y-%m-%d"),
            "lead": {
                "id": lead.get("id"),
                "name": lead.get("name"),
                "status_id": lead.get("status_id"),
                "pipeline_id": lead.get("pipeline_id"),
                "price": lead.get("price"),
                "phone": context.phone,
            },
            "warning": context.warning,
            "call_analyses": context.call_analyses[-3:],
            "fresh_audio_transcripts": [
                {**item, "transcript": clip(item.get("transcript", ""), 5000)}
                for item in context.audio_transcripts[-2:]
            ],
            "telegram_messages": context.telegram_messages[-30:],
            "open_oisha_tasks": [
                {"id": task.get("id"), "text": task.get("text")}
                for task in context.open_tasks
                if str(task.get("text") or "").startswith(("Oisha audit:", "Oisha smart:"))
            ],
        }

        prompt = (
            "Siz amoCRM ekspertisiz. Quyidagi lead bo'yicha real suhbat kontekstidan "
            "bitta aniq keyingi qadam taskini chiqaring.\n\n"
            "Qoidalar:\n"
            "- Audio/transkript va Telegram tarixiga tayaning, taxmin uydirmang.\n"
            "- Agar suhbat shaxsiy/oila/jamoa bo'lsa, sotuv taski qo'ymang; CRMdan ajratish yoki review task bering.\n"
            "- Agar mijoz bo'lsa, task aniq bo'lsin: kimga nima yuborish, nimani tekshirish, qachon follow-up.\n"
            "- Agar warning bo'lsa, transkriptni past ishonch bilan baholang.\n"
            "- due_in_hours: hot lead 4-6, warm 24, reactivation/cold 48, non-client review 24.\n"
            "- tags 2-5 ta bo'lsin, OISHA_SMART_ prefiksi bilan.\n\n"
            "Faqat JSON qaytaring:\n"
            "{\n"
            '  "category": "Mijoz|Shaxsiy|Oila|Jamoa|Boshqa",\n'
            '  "qualification": "hot|warm|cold|not_client|team|personal|needs_context",\n'
            '  "confidence": 0.0,\n'
            "  \"summary\": \"O'zbek lotinida 2-4 gap\",\n"
            '  "next_task_text": "aniq task matni",\n'
            '  "due_in_hours": 24,\n'
            '  "tags": ["OISHA_SMART_MIJoz"],\n'
            '  "evidence": ["qaysi suhbatdan xulosa olindi"]\n'
            "}\n\n"
            f"Kontekst JSON:\n{json.dumps(payload, ensure_ascii=False, default=str)}"
        )

        response = await self.genai_client.aio.models.generate_content(
            model=getattr(settings, "GEMINI_CALL_MODEL", "gemini-2.5-flash") or "gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
                max_output_tokens=1800,
            ),
        )
        data = extract_json(getattr(response, "text", "") or "")
        return self.normalize_decision(data, context)

    def normalize_decision(self, data: dict[str, Any], context: LeadContext) -> SmartDecision:
        category = str(data.get("category") or "Boshqa").strip()
        if category not in {"Mijoz", "Shaxsiy", "Oila", "Jamoa", "Boshqa"}:
            category = "Boshqa"
        qualification = str(data.get("qualification") or "needs_context").strip().lower()
        confidence = float(data.get("confidence") or 0.4)
        task = str(data.get("next_task_text") or "").strip()
        if not task:
            task = self.fallback_decision(context).next_task_text
        if not task.startswith(SMART_TASK_PREFIX):
            task = f"{SMART_TASK_PREFIX} {task}"
        due = int(data.get("due_in_hours") or 24)
        tags = [str(tag).strip() for tag in data.get("tags") or [] if str(tag).strip()]
        tags = [tag if tag.startswith("OISHA_SMART_") else f"OISHA_SMART_{tag.upper()}" for tag in tags]
        if not tags:
            tags = [f"OISHA_SMART_{category.upper()}"]
        return SmartDecision(
            category=category,
            qualification=qualification,
            confidence=max(0.0, min(1.0, confidence)),
            summary=clip(str(data.get("summary") or ""), 1500) or self.fallback_decision(context).summary,
            next_task_text=clip(task, 900),
            due_in_hours=max(1, min(due, 168)),
            tags=list(dict.fromkeys(tags[:5])),
            evidence=[clip(str(item), 300) for item in (data.get("evidence") or [])[:6]],
        )

    def fallback_decision(self, context: LeadContext) -> SmartDecision:
        latest = context.call_analyses[-1] if context.call_analyses else {}
        category = str(latest.get("category") or "Boshqa").strip() or "Boshqa"
        summary = str(latest.get("summary") or latest.get("clean_snippet") or "").strip()
        next_steps = str(latest.get("next_steps") or "").strip()
        text_blob = " ".join(
            [
                summary,
                next_steps,
                " ".join(m.get("text", "") for m in context.telegram_messages[-10:]),
            ]
        ).lower()

        business_words = ["patent", "logo", "brend", "branding", "dizayn", "smm", "sayt", "narx", "to'lov", "tolov", "kp", "brief"]
        personal_words = ["oila", "do'kon", "uy", "kelyapman", "qarindosh", "aka hozir", "shaxsiy"]

        if context.warning and not context.audio_transcripts:
            return SmartDecision(
                category="Boshqa",
                qualification="needs_context",
                confidence=0.35,
                summary=context.warning,
                next_task_text=(
                    f"{SMART_TASK_PREFIX} STT ogohlantirishi bor. Leadni qo'lda tekshirib, "
                    "suhbat mijozmi yoki shaxsiy ekanini aniqlang; keyin statusni tozalang."
                ),
                due_in_hours=24,
                tags=["OISHA_SMART_NEEDS_RELISTEN"],
                evidence=["amoCRM note ichida STT xatolik ogohlantirishi bor"],
            )

        if any(word in text_blob for word in business_words) or category == "Mijoz":
            task = next_steps if next_steps and next_steps.lower() not in {"n/a", "yo'q", "yoq"} else ""
            if not task:
                task = "Mijoz bilan ehtiyoj, budjet va muddatni aniqlab, brief yoki uchrashuvga olib kiring."
            return SmartDecision(
                category="Mijoz",
                qualification="warm",
                confidence=0.65 if summary else 0.45,
                summary=summary or "Mijoz konteksti bor, lekin xulosa cheklangan.",
                next_task_text=f"{SMART_TASK_PREFIX} {task}",
                due_in_hours=24,
                tags=["OISHA_SMART_MIJoz", "OISHA_SMART_WARM"],
                evidence=["call/telegram matnida biznes ehtiyoj signali bor"],
            )

        if category in {"Shaxsiy", "Oila"} or any(word in text_blob for word in personal_words):
            return SmartDecision(
                category=category if category in {"Shaxsiy", "Oila"} else "Shaxsiy",
                qualification="personal",
                confidence=0.55,
                summary=summary or "Suhbat biznes leadga o'xshamaydi.",
                next_task_text=(
                    f"{SMART_TASK_PREFIX} Bu lead shaxsiy/oila aralashmasi bo'lishi mumkin. "
                    "CRMdan ajratish yoki Lost reason bilan yopishni tekshiring."
                ),
                due_in_hours=24,
                tags=["OISHA_SMART_PERSONAL_REVIEW"],
                evidence=["suhbatda biznes ehtiyoj aniqlanmadi"],
            )

        if context.call_analyses:
            latest_call = context.call_analyses[-1]
            return SmartDecision(
                category=category if category in {"Jamoa", "Boshqa"} else "Boshqa",
                qualification="needs_context",
                confidence=0.45,
                summary=summary or "Call transcript bor, lekin mijoz ehtiyoji aniq ajralmadi.",
                next_task_text=(
                    f"{SMART_TASK_PREFIX} Qo'ng'iroq transkriptini qo'lda tekshiring: "
                    "bu real mijoz suhbatimi, shaxsiy/jamoa suhbatimi yoki reactivationmi. "
                    "Natijaga qarab status/tagni yangilang."
                ),
                due_in_hours=24,
                tags=["OISHA_SMART_CALL_REVIEW"],
                evidence=[
                    f"call_id={latest_call.get('call_id') or 'unknown'}",
                    "call transcript bor, ammo keyingi sotuv qadami aniq emas",
                ],
            )

        return SmartDecision(
            category="Boshqa",
            qualification="needs_context",
            confidence=0.3,
            summary=summary or "Audio/Telegram kontekst yetarli emas.",
            next_task_text=(
                f"{SMART_TASK_PREFIX} Telefon/Telegram tarixini to'ldiring: lead uchun real suhbat "
                "konteksti topilmadi. Raqamni tekshirib, keyin mijoz/shaxsiy/spam deb ajrating."
            ),
            due_in_hours=24,
            tags=["OISHA_SMART_NEEDS_CONTEXT"],
            evidence=["call transcript yoki Telegram history topilmadi"],
        )

    def smart_task_exists(self, tasks: list[dict[str, Any]]) -> bool:
        return any(str(task.get("text") or "").startswith(SMART_TASK_PREFIX) for task in tasks)

    def generic_tasks(self, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [task for task in tasks if str(task.get("text") or "").startswith(GENERIC_TASK_PREFIX)]

    async def apply_decision(self, context: LeadContext, decision: SmartDecision) -> None:
        lead_id = context.lead_id
        if self.smart_task_exists(context.open_tasks) and not self.force:
            self.record("smart_task_skipped_exists", lead_id)
            await self.close_generic_tasks(context)
            return

        note_text = self.format_note(context, decision)
        complete_till = int((self.now + timedelta(hours=decision.due_in_hours)).timestamp())

        self.record(
            "smart_plan",
            lead_id,
            decision=asdict(decision),
            phone=context.phone,
            call_analyses=len(context.call_analyses),
            audio_transcripts=len(context.audio_transcripts),
            telegram_messages=len(context.telegram_messages),
        )
        if self.dry_run:
            return

        if any(SMART_NOTE_MARKER in text_from_note(note) for note in context.notes) and not self.force:
            self.record("smart_note_skipped_exists", lead_id)
        else:
            try:
                note_response = self.request(
                    "POST",
                    f"/api/v4/leads/{lead_id}/notes",
                    json_payload=[{"note_type": "common", "params": {"text": note_text}}],
                )
                if note_response.status_code not in {200, 201}:
                    self.record_error("add_smart_note", lead_id, f"HTTP {note_response.status_code}: {note_response.text[:400]}")
                else:
                    self.record("smart_note_added", lead_id)
            except Exception as exc:
                self.record_error("add_smart_note", lead_id, str(exc))

        for tag in decision.tags:
            try:
                tag_response = self.request(
                    "PATCH",
                    f"/api/v4/leads/{lead_id}",
                    json_payload={"_embedded": {"tags": [{"name": tag}]}},
                )
                if tag_response.status_code != 200:
                    self.record_error("add_smart_tag", lead_id, f"{tag}: HTTP {tag_response.status_code}")
                else:
                    self.record("smart_tag_added", lead_id, tag=tag)
            except Exception as exc:
                self.record_error("add_smart_tag", lead_id, f"{tag}: {exc}")

        try:
            task_result = await self.amocrm.create_task(
                element_id=lead_id,
                text=decision.next_task_text,
                complete_till=complete_till,
                responsible_user_id=context.lead.get("responsible_user_id"),
            )
            if task_result:
                self.record("smart_task_created", lead_id, due_in_hours=decision.due_in_hours)
                await self.close_generic_tasks(context)
            else:
                self.record_error("create_smart_task", lead_id, self.amocrm.last_error or "task_create_failed")
        except Exception as exc:
            self.record_error("create_smart_task", lead_id, str(exc))

    def format_note(self, context: LeadContext, decision: SmartDecision) -> str:
        lead = context.lead
        calls = []
        for item in context.call_analyses[-2:]:
            calls.append(
                "- "
                + "; ".join(
                    part
                    for part in [
                        f"Call ID {item.get('call_id')}" if item.get("call_id") else "",
                        f"Toifa {item.get('category')}" if item.get("category") else "",
                        clip(item.get("summary", ""), 350),
                        f"Keyingi: {clip(item.get('next_steps', ''), 250)}" if item.get("next_steps") else "",
                    ]
                    if part
                )
            )
        telegram = "\n".join(
            f"- {msg.get('role')}: {clip(msg.get('text', ''), 220)}"
            for msg in context.telegram_messages[-6:]
        )
        evidence = "\n".join(f"- {item}" for item in decision.evidence[:6]) or "- dalil cheklangan"
        return clip(
            f"""{SMART_NOTE_MARKER}
Lead: {lead.get('name')} (#{context.lead_id})
Telefon: {context.phone or 'topilmadi'}

Kategoriya: {decision.category}
Qualification: {decision.qualification}
Ishonch: {decision.confidence:.2f}

Xulosa:
{decision.summary}

Keyingi task:
{decision.next_task_text}
Deadline: {decision.due_in_hours} soat ichida

Dalillar:
{evidence}

Call kontekst:
{chr(10).join(calls) if calls else '- call transcript topilmadi'}

Telegram kontekst:
{telegram if telegram else '- Telegram tarix topilmadi'}

Ogohlantirish:
{context.warning or '-'}
""",
            9000,
        )

    async def close_generic_tasks(self, context: LeadContext) -> None:
        generic = self.generic_tasks(context.open_tasks)
        if not generic:
            return
        for task in generic:
            task_id = int(task["id"])
            self.record("generic_task_would_close" if self.dry_run else "generic_task_close", context.lead_id, task_id=task_id)
            if self.dry_run:
                continue
            try:
                response = self.request(
                    "PATCH",
                    f"/api/v4/tasks/{task_id}",
                    json_payload={
                        "is_completed": True,
                        "result": {"text": "Replaced by contextual Oisha smart task."},
                    },
                )
                if response.status_code != 200:
                    self.record_error("close_generic_task", context.lead_id, f"task {task_id}: HTTP {response.status_code}: {response.text[:300]}")
            except Exception as exc:
                self.record_error("close_generic_task", context.lead_id, f"task {task_id}: {exc}")

    def save_report(self) -> Path:
        report = {
            "ok": not self.errors,
            "generated_at": self.now.isoformat(),
            "dry_run": self.dry_run,
            "limit": self.limit,
            "only_with_context": self.only_with_context,
            "use_userbot": self.use_userbot,
            "force": self.force,
            "summary": {
                "actions_total": len(self.actions),
                "errors_total": len(self.errors),
                "smart_plans": sum(1 for a in self.actions if a["action"] == "smart_plan"),
                "smart_tasks_created": sum(1 for a in self.actions if a["action"] == "smart_task_created"),
                "generic_tasks_closed": sum(1 for a in self.actions if a["action"] == "generic_task_close"),
                "audio_transcribed": sum(1 for a in self.actions if a["action"] == "audio_transcribed"),
            },
            "actions": self.actions,
            "errors": self.errors,
        }
        mode = "dry_run" if self.dry_run else "live"
        path = self.report_dir / f"amocrm_smart_lead_tasks_{mode}_{self.stamp}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return path

    async def run(self, lead_ids: list[int] | None = None) -> dict[str, Any]:
        await self.setup()
        try:
            open_tasks_by_lead = self.fetch_open_tasks()
            if lead_ids:
                candidates = []
                for lead_id in lead_ids:
                    lead = self.fetch_lead(lead_id)
                    if lead:
                        candidates.append(lead)
            else:
                candidates = self.fetch_candidate_leads()
            processed = 0
            inspected = 0

            for lead in candidates:
                if processed >= self.limit:
                    break
                inspected += 1
                lead_id = int(lead["id"])
                lead_open_tasks = open_tasks_by_lead.get(lead_id, [])
                if not self.force and self.smart_task_exists(lead_open_tasks):
                    self.record("lead_skipped_smart_exists", lead_id)
                    continue

                context = await self.build_context(lead, lead_open_tasks)
                if self.only_with_context and not context.has_context():
                    self.record("lead_skipped_no_context", lead_id)
                    continue

                decision = await self.decide(context)
                await self.apply_decision(context, decision)
                processed += 1
                if not self.dry_run:
                    await asyncio.sleep(0.35)

            report_path = self.save_report()
            return {
                "ok": not self.errors,
                "dry_run": self.dry_run,
                "inspected": inspected,
                "processed": processed,
                "actions_total": len(self.actions),
                "errors_total": len(self.errors),
                "report_path": str(report_path.resolve()),
            }
        finally:
            await self.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create smart amoCRM tasks from call + Telegram context")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--live", action="store_true")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--lead-id", type=int, action="append", default=[])
    parser.add_argument("--all", action="store_true", help="Process leads even when no call/Telegram context is found")
    parser.add_argument("--no-userbot", action="store_true", help="Disable live Telegram userbot history lookup")
    parser.add_argument("--force", action="store_true", help="Create a new smart task even if one already exists")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    pipeline = SmartLeadTaskPipeline(
        dry_run=args.dry_run,
        limit=args.limit,
        only_with_context=not args.all,
        use_userbot=not args.no_userbot,
        force=args.force,
    )
    result = await pipeline.run(lead_ids=args.lead_id or None)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())

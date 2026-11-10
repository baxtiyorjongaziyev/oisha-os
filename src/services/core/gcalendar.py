import os
import uuid
import logging
from typing import Any, Dict, Optional

from src.services.core.google_oauth import (
    GOOGLE_USER_SCOPES,
    load_user_credentials,
)

try:
    from google.oauth2.service_account import Credentials as ServiceAccountCredentials
    from googleapiclient.discovery import build
except ImportError:
    ServiceAccountCredentials = None
    build = None

logger = logging.getLogger(__name__)

DEFAULT_CALENDAR_ID = "primary"
DEFAULT_CREDENTIALS_PATH = "service_account.json"
DEFAULT_CREDENTIALS_ENV = "GOOGLE_CALENDAR_CREDENTIALS_PATH"
DEFAULT_CREDENTIALS_FALLBACKS = (
    "/home/ubuntu/oisha-secrets/service_account_calendar.json",
    "/home/ubuntu/.secrets/service_account_calendar.json",
)
DEFAULT_OAUTH_FILE = "token.json"
CALENDAR_TIMEZONE = "Asia/Tashkent"


def _stringify_private(properties: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """Google Calendar extendedProperties faqat matn qiymatlarini qabul qiladi."""
    result: Dict[str, str] = {}
    for key, value in (properties or {}).items():
        if value is None or value == "":
            continue
        result[str(key)] = str(value)
    return result


def _is_missing_event_error(exc: Exception) -> bool:
    status = getattr(getattr(exc, "resp", None), "status", None)
    text = str(exc)
    return status in (404, 410) or "404" in text or "410" in text


class GoogleCalendarSync:
    def __init__(
        self,
        credentials_path: Optional[str] = None,
        calendar_id: Optional[str] = None,
        token_path: Optional[str] = None,
    ):
        self.credentials_path = (
            os.getenv("GOOGLE_CALENDAR_CREDENTIALS_PATH")
            or credentials_path
            or DEFAULT_CREDENTIALS_PATH
        )
        self.credentials_path_env = os.getenv(DEFAULT_CREDENTIALS_ENV, "").strip()
        self.calendar_id = (
            calendar_id or os.getenv("GOOGLE_CALENDAR_ID") or DEFAULT_CALENDAR_ID
        )
        self.token_path = token_path or os.getenv(
            "GOOGLE_CALENDAR_TOKEN_PATH", DEFAULT_OAUTH_FILE
        )
        self.service = None
        self.scopes = list(GOOGLE_USER_SCOPES)
        self._authenticate()

    def _service_account_candidates(self) -> list[str]:
        """Calendar service-account keys, env-scoped key first."""
        candidates = [
            self.credentials_path_env,
            self.credentials_path,
            *DEFAULT_CREDENTIALS_FALLBACKS,
        ]
        unique: list[str] = []
        for path in candidates:
            if path and path not in unique:
                unique.append(path)
        return unique

    def _authenticate(self) -> None:
        """Google API bilan avtorizatsiya (JSON token yoki Service Account)."""
        creds = load_user_credentials(self.token_path, self.scopes)
        if creds:
            logger.info("[GCALENDAR OK] Shaxsiy Google akkaunti (Token) ishga tushdi.")

        if not creds:
            checked = self._service_account_candidates()
            for path in checked:
                if not os.path.exists(path):
                    continue
                try:
                    creds = ServiceAccountCredentials.from_service_account_file(
                        path, scopes=self.scopes
                    )
                    logger.info(
                        f"[GCALENDAR OK] Service Account ulandi ({path})."
                    )
                    break
                except Exception as e:
                    logger.error(
                        "[GCALENDAR] Service Account avtorizatsiyasida xato "
                        f"({path}): {e}"
                    )
            if not creds:
                logger.warning(
                    "[GCALENDAR] Avtorizatsiya fayli topilmadi: "
                    f"{self.token_path} yoki {', '.join(checked)}"
                )

        if creds:
            self.service = build("calendar", "v3", credentials=creds)
            logger.info(f"[GCALENDAR] Kalendar ID: {self.calendar_id}")
        else:
            logger.error("[GCALENDAR] Avtorizatsiya muvaffaqiyatsiz tugadi.")

    def _build_event_body(
        self,
        summary: str,
        start_time: str,
        end_time: str,
        description: str = "",
        location: str = "",
        extended_properties: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "summary": summary,
            "location": location,
            "description": description,
            "start": {"dateTime": start_time, "timeZone": CALENDAR_TIMEZONE},
            "end": {"dateTime": end_time, "timeZone": CALENDAR_TIMEZONE},
            "conferenceData": {
                "createRequest": {
                    "requestId": str(uuid.uuid4()),
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            },
            "reminders": {"useDefault": True},
        }
        private = _stringify_private(extended_properties)
        if private:
            body["extendedProperties"] = {"private": private}
        return body

    def _insert_event(self, body: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return self.service.events().insert(
                calendarId=self.calendar_id, body=body, conferenceDataVersion=1
            ).execute()
        except Exception as conference_exc:
            if "Invalid conference type value" not in str(conference_exc):
                raise
            logger.warning(
                "[GCALENDAR] Meet link yaratilmadi; oddiy event bilan qayta uriniladi."
            )
            fallback = dict(body)
            fallback.pop("conferenceData", None)
            return self.service.events().insert(
                calendarId=self.calendar_id, body=fallback
            ).execute()

    def create_event(
        self,
        summary: str,
        start_time: str,
        end_time: str,
        description: str = "",
        location: str = "",
        extended_properties: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Yangi kalendar tadbiri yaratadi va event resursini qaytaradi.

        start_time va end_time ISO formatda boʻlishi kerak
        (masalan: 2026-05-14T13:00:00+05:00).
        """
        if not self.service:
            logger.error("[GCALENDAR] Service ulanmagan.")
            return None

        try:
            body = self._build_event_body(
                summary=summary,
                start_time=start_time,
                end_time=end_time,
                description=description,
                location=location,
                extended_properties=extended_properties,
            )
            event = self._insert_event(body)
            logger.info(f"[GCALENDAR OK] Tadbir yaratildi: {event.get('htmlLink')}")
            return event
        except Exception as e:
            logger.error(f"[GCALENDAR ERROR] Tadbir yaratishda xato: {e}")
            return None

    def update_event(
        self,
        event_id: str,
        summary: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        description: Optional[str] = None,
        location: Optional[str] = None,
        extended_properties: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Mavjud tadbirni qisman yangilaydi (patch) va event resursini qaytaradi."""
        if not self.service or not event_id:
            logger.error("[GCALENDAR] Tadbirni yangilash uchun service yoki ID yoʻq.")
            return None

        body: Dict[str, Any] = {}
        if summary is not None:
            body["summary"] = summary
        if description is not None:
            body["description"] = description
        if location is not None:
            body["location"] = location
        if start_time is not None:
            body["start"] = {"dateTime": start_time, "timeZone": CALENDAR_TIMEZONE}
        if end_time is not None:
            body["end"] = {"dateTime": end_time, "timeZone": CALENDAR_TIMEZONE}
        private = _stringify_private(extended_properties)
        if private:
            body["extendedProperties"] = {"private": private}
        if not body:
            return None

        try:
            event = self.service.events().patch(
                calendarId=self.calendar_id, eventId=str(event_id), body=body
            ).execute()
            logger.info(f"[GCALENDAR OK] Tadbir yangilandi: {event_id}")
            return event
        except Exception as e:
            logger.error(f"[GCALENDAR ERROR] Tadbirni yangilashda xato: {e}")
            return None

    def delete_event(self, event_id: str) -> bool:
        """Tadbirni oʻchiradi. Allaqachon oʻchirilgan boʻlsa ham True qaytaradi."""
        if not self.service or not event_id:
            logger.error("[GCALENDAR] Tadbirni oʻchirish uchun service yoki ID yoʻq.")
            return False

        try:
            self.service.events().delete(
                calendarId=self.calendar_id, eventId=str(event_id)
            ).execute()
            logger.info(f"[GCALENDAR OK] Tadbir oʻchirildi: {event_id}")
            return True
        except Exception as e:
            if _is_missing_event_error(e):
                logger.info(f"[GCALENDAR] Tadbir allaqachon yoʻq: {event_id}")
                return True
            logger.error(f"[GCALENDAR ERROR] Tadbirni oʻchirishda xato: {e}")
            return False

    def get_upcoming_events(self, date_str=None, limit=10):
        """Maʼlum bir kun (yoki bugun) uchun barcha tadbirlar roʻyxatini olish.

        date_str: YYYY-MM-DD
        """
        if not self.service:
            return []

        import datetime
        from zoneinfo import ZoneInfo

        tz = ZoneInfo(CALENDAR_TIMEZONE)

        if not date_str:
            target_date = datetime.datetime.now(tz)
        else:
            target_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").replace(
                tzinfo=tz
            )

        time_min = target_date.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        time_max = target_date.replace(hour=23, minute=59, second=59, microsecond=0).isoformat()

        try:
            events_result = (
                self.service.events()
                .list(
                    calendarId=self.calendar_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    maxResults=limit,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
            return events_result.get("items", [])
        except Exception as e:
            logger.error(f"[GCALENDAR ERROR] Tadbirlarni roʻyxatlashda xato: {e}")
            return []

    def get_current_event(self):
        """Hozirgi vaqtda davom etayotgan tadbirni olish."""
        if not self.service:
            return None

        import datetime

        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        try:
            events_result = (
                self.service.events()
                .list(
                    calendarId=self.calendar_id,
                    timeMin=now,
                    maxResults=1,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
            events = events_result.get("items", [])

            if not events:
                return None

            event = events[0]
            start = event["start"].get("dateTime", event["start"].get("date"))
            start_dt = datetime.datetime.fromisoformat(start.replace("Z", "+00:00"))
            now_dt = datetime.datetime.now(datetime.timezone.utc)

            if start_dt <= now_dt:
                return event

            return None
        except Exception as e:
            logger.error(f"[GCALENDAR ERROR] Tadbirni olishda xato: {e}")
            return None

    def get_free_slots(self, date_str=None):
        """Maʼlum bir kun (yoki bugun/ertaga) uchun boʻsh uchrashuv vaqtlarini olish."""
        import datetime
        from zoneinfo import ZoneInfo

        tz = ZoneInfo(CALENDAR_TIMEZONE)
        if not date_str:
            target_date = datetime.datetime.now(tz)
        else:
            try:
                target_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").replace(
                    tzinfo=tz
                )
            except ValueError:
                target_date = datetime.datetime.now(tz)

        start_of_day = target_date.replace(hour=10, minute=0, second=0, microsecond=0)
        end_of_day = target_date.replace(hour=18, minute=0, second=0, microsecond=0)

        if not self.service:
            logger.error("[GCALENDAR ERROR] xizmat ulanmagan.")
            return ["11:00", "15:00", "17:00"]

        try:
            time_min = target_date.replace(
                hour=0, minute=0, second=0, microsecond=0
            ).isoformat()
            time_max = target_date.replace(
                hour=23, minute=59, second=59, microsecond=0
            ).isoformat()

            events_result = (
                self.service.events()
                .list(
                    calendarId=self.calendar_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
            events = events_result.get("items", [])

            busy_slots = []
            for event in events:
                start = event["start"].get("dateTime", event["start"].get("date"))
                end = event["end"].get("dateTime", event["end"].get("date"))
                if "T" in start:
                    busy_slots.append((
                        datetime.datetime.fromisoformat(start).astimezone(tz),
                        datetime.datetime.fromisoformat(end).astimezone(tz),
                    ))

            free_slots = []
            current_slot = start_of_day
            while current_slot < end_of_day:
                slot_end = current_slot + datetime.timedelta(hours=1)

                is_free = True
                for b_start, b_end in busy_slots:
                    if (current_slot < b_end) and (slot_end > b_start):
                        is_free = False
                        break

                if is_free and current_slot > datetime.datetime.now(tz):
                    free_slots.append(current_slot.strftime("%H:%M"))

                current_slot += datetime.timedelta(hours=1)

            if not free_slots and not date_str:
                next_day = (target_date + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
                return self.get_free_slots(next_day)

            date_formatted = target_date.strftime("%Y-%m-%d")
            return (
                [f"{date_formatted} sanasidagi: {slot}" for slot in free_slots]
                if free_slots
                else []
            )

        except Exception as e:
            logger.error(f"[GCALENDAR SLOTS] xato: {e}")
            return ["10:00", "14:00", "16:00"]

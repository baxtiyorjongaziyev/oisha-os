import os
import logging
import pickle
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)


class GoogleCalendarSync:
    def __init__(self, credentials_path="service_account.json"):
        self.credentials_path = credentials_path
        self.service = None
        self.scopes = ["https://www.googleapis.com/auth/calendar.events"]
        self._authenticate()

    def _authenticate(self):
        """Google API bilan avtorizatsiya (Token yoki Service Account)."""
        creds = None
        # 1. token.pickle - Shaxsiy akkaunt (OAuth2)
        if os.path.exists("token.pickle"):
            try:
                with open("token.pickle", "rb") as token:
                    creds = pickle.load(token)  # nosec
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                    with open("token.pickle", "wb") as token:
                        pickle.dump(creds, token)
                logger.info(
                    "[GCALENDAR OK] Shaxsiy Google akkaunti (Token) ishga tushdi."
                )
            except Exception as e:
                logger.error(f"[GCALENDAR] Token yangilashda xato: {e}")
                creds = None

        # 2. service_account.json (Fallback)
        if not creds:
            if os.path.exists(self.credentials_path):
                try:
                    creds = ServiceAccountCredentials.from_service_account_file(
                        self.credentials_path, scopes=self.scopes
                    )
                    logger.info("[GCALENDAR OK] Service Account ulandi.")
                except Exception as e:
                    logger.error(
                        f"[GCALENDAR] Service Account avtorizatsiyasida xato: {e}"
                    )
            else:
                logger.warning("[GCALENDAR] Avtorizatsiya fayli topilmadi.")

        if creds:
            self.service = build("calendar", "v3", credentials=creds)
        else:
            logger.error("[GCALENDAR] Avtorizatsiya muvaffaqiyatsiz tugadi.")

    def create_event(self, summary, start_time, end_time, description="", location=""):
        """Yangi kalendar tadbiri yaratish.
        start_time va end_time ISO formatda bo'lishi kerak (masalan: 2024-05-28T10:00:00Z)
        """
        if not self.service:
            logger.error("[GCALENDAR] Service ulanmagan.")
            return False

        try:
            import uuid

            request_id = str(uuid.uuid4())
            event = {
                "summary": summary,
                "location": location,
                "description": description,
                "start": {
                    "dateTime": start_time,
                    "timeZone": "Asia/Tashkent",
                },
                "end": {
                    "dateTime": end_time,
                    "timeZone": "Asia/Tashkent",
                },
                "conferenceData": {
                    "createRequest": {
                        "requestId": request_id,
                        "conferenceSolutionKey": {"type": "hangoutsMeet"},
                    }
                },
                "reminders": {
                    "useDefault": True,
                },
            }

            event = (
                self.service.events()
                .insert(calendarId="primary", body=event, conferenceDataVersion=1)
                .execute()
            )

            logger.info(f"[GCALENDAR OK] Tadbir yaratildi: {event.get('htmlLink')}")
            return True
        except Exception as e:
            logger.error(f"[GCALENDAR ERROR] Tadbir yaratishda xato: {e}")
            return False

    def get_upcoming_events(self, date_str=None, limit=10):
        """Ma'lum bir kun (yoki bugun) uchun barcha tadbirlarni ro'yxatini olish.
        date_str: YYYY-MM-DD
        """
        if not self.service:
            return []

        import datetime
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("Asia/Tashkent")

        if not date_str:
            target_date = datetime.datetime.now(tz)
        else:
            target_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").replace(
                tzinfo=tz
            )

        time_min = target_date.replace(
            hour=0, minute=0, second=0, microsecond=0
        ).isoformat()
        time_max = target_date.replace(
            hour=23, minute=59, second=59, microsecond=0
        ).isoformat()

        try:
            events_result = (
                self.service.events()
                .list(
                    calendarId="primary",
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
            logger.error(f"[GCALENDAR ERROR] Tadbirlarni ro'yxatlashda xato: {e}")
            return []

    def get_current_event(self):
        """Hozirgi vaqtda davom etayotgan tadbirni olish."""
        if not self.service:
            return None

        import datetime

        now = datetime.datetime.utcnow().isoformat() + "Z"

        try:
            # Hozirdan keyingi 1 ta tadbirni olish
            events_result = (
                self.service.events()
                .list(
                    calendarId="primary",
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

            # Agar tadbir hozir boshlangan bo'lsa (yoki boshlanish arafasida bo'lsa)
            # API da timeMin=now faqatgina kelajakdagilarni yoki hozir tugamaganlarni qaytaradi
            # Biz tadbir haqiqatdan ham hozir faol ekanligini tekshiramiz
            start_dt = datetime.datetime.fromisoformat(start.replace("Z", "+00:00"))
            now_dt = datetime.datetime.now(datetime.timezone.utc)

            if start_dt <= now_dt:
                return event

            return None
        except Exception as e:
            logger.error(f"[GCALENDAR ERROR] Tadbirni olishda xato: {e}")
            return None

    def get_free_slots(self, date_str=None):
        """Ma'lum bir kun (yoki bugun/ertaga) uchun bo'sh uchrashuv vaqtlarini olish (10:00-18:00 oraliqda).
        Kutilayotgan date_str formati: YYYY-MM-DD
        """
        import datetime
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("Asia/Tashkent")
        if not date_str:
            target_date = datetime.datetime.now(tz)
        else:
            try:
                target_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").replace(
                    tzinfo=tz
                )
            except ValueError:
                target_date = datetime.datetime.now(tz)

        # 10:00 dan 18:00 gacha bo'lgan oraliq ish vaqti deb faraz qilinadi (1 soatlik slotlar)
        start_of_day = target_date.replace(hour=10, minute=0, second=0, microsecond=0)
        end_of_day = target_date.replace(hour=18, minute=0, second=0, microsecond=0)

        if not self.service:
            logger.error("[GCALENDAR ERROR] xizmat ulanmagan.")
            # Default slolarni qaytarish (agar API ishlamay qolsa ehtiyot uchun)
            return ["11:00", "15:00", "17:00"]

        try:
            # Shu kundagi barcha eventlarni olish
            time_min = target_date.replace(
                hour=0, minute=0, second=0, microsecond=0
            ).isoformat()
            time_max = target_date.replace(
                hour=23, minute=59, second=59, microsecond=0
            ).isoformat()

            events_result = (
                self.service.events()
                .list(
                    calendarId="primary",
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
                    busy_slots.append(
                        (
                            datetime.datetime.fromisoformat(start).astimezone(tz),
                            datetime.datetime.fromisoformat(end).astimezone(tz),
                        )
                    )

            free_slots = []
            current_slot = start_of_day
            while current_slot < end_of_day:
                slot_end = current_slot + datetime.timedelta(hours=1)

                # Check if this slot overlaps with any busy slot
                is_free = True
                for b_start, b_end in busy_slots:
                    if (current_slot < b_end) and (slot_end > b_start):
                        is_free = False
                        break

                # Vaqt o'tib ketmaganligini tekshirish
                if is_free and current_slot > datetime.datetime.now(tz):
                    free_slots.append(current_slot.strftime("%H:%00"))

                current_slot += datetime.timedelta(hours=1)

            # Agar bugun bo'sh bo'lmasa yoki vaqt o'tib ketgan bo'lsa, ertangi kunni qidiramiz
            if not free_slots and not date_str:
                next_day = (target_date + datetime.timedelta(days=1)).strftime(
                    "%Y-%m-%d"
                )
                return self.get_free_slots(next_day)

            # Qaysi kunga oidligini bildirish uchun sana bilan qo'shib qaytarish (ixtiyoriy, userbotga yordam)
            date_formatted = target_date.strftime("%Y-%m-%d")
            return (
                [f"{date_formatted} tahriridagi: {slot}" for slot in free_slots]
                if free_slots
                else []
            )

        except Exception as e:
            logger.error(f"[GCALENDAR SLOTS] xato: {e}")
            return ["10:00", "14:00", "16:00"]


if __name__ == "__main__":
    # Test qilish
    logging.basicConfig(level=logging.INFO)
    sync = GoogleCalendarSync()
    if sync.service:
        # Namuna: Bugun soat 15:00 dan 16:00 gacha
        import datetime

        now = datetime.datetime.now()
        start = now.replace(hour=15, minute=0, second=0, microsecond=0).isoformat()
        end = now.replace(hour=16, minute=0, second=0, microsecond=0).isoformat()
        sync.create_event("Test Meeting", start, end, "AI tomonidan yaratildi")

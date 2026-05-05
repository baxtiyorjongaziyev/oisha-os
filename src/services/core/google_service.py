import logging
from src.services.core.gsheets import GoogleSheetsSync
from src.services.core.gcalendar import GoogleCalendarSync
from src.services.core.gcontacts import GoogleContactsSync
from src.services.core.gdrive import GoogleDriveSync
from src import config

logger = logging.getLogger(__name__)


class GoogleService:
    def __init__(self):
        self.creds_file = config.GSHEET_CREDS_FILE
        try:
            self.sheets = GoogleSheetsSync(config.GSHEET_ID, self.creds_file)
        except Exception as e:
            logger.warning(f"?? [GOOGLE] Sheets init failed: {e}")
            self.sheets = None
        try:
            self.calendar = GoogleCalendarSync(self.creds_file)
        except Exception as e:
            logger.warning(f"?? [GOOGLE] Calendar init failed: {e}")
            self.calendar = None
        try:
            self.contacts = GoogleContactsSync(self.creds_file)
        except Exception as e:
            logger.warning(f"?? [GOOGLE] Contacts init failed: {e}")
            self.contacts = None
        try:
            self.drive = GoogleDriveSync(self.creds_file)
        except Exception as e:
            logger.warning(f"?? [GOOGLE] Drive init failed: {e}")
            self.drive = None

    async def log_user_action(self, user_id, name, action):
        if self.sheets:
            self.sheets.log_message(user_id, action, is_ai=False)

    async def schedule_meeting(self, summary, start_time, end_time=None):
        if self.calendar:
            return self.calendar.create_event(summary, start_time, end_time)
        return None

    async def save_contact(self, name, phones, notes=None, group_name="TEZ NATIJA 5"):
        if not self.contacts:
            return None
        parts = name.split()
        first = parts[0] if parts else "Unknown"
        last = " ".join(parts[1:]) if len(parts) > 1 else ""
        return self.contacts.create_contact(first, last, phones, notes, group_name)

import gspread
from google.oauth2.service_account import Credentials
import os
import logging
import datetime

logger = logging.getLogger(__name__)

class GoogleSheetsSync:
    def __init__(self, spreadsheet_id, credentials_path="service_account.json"):
        self.spreadsheet_id = spreadsheet_id
        self.credentials_path = credentials_path
        self.client = None
        self.spreadsheet = None
        self.sheet = None
        self.log_sheet = None
        self._authenticate()

    def _authenticate(self):
        """Google API bilan avtorizatsiya."""
        if not os.path.exists(self.credentials_path):
            logger.warning(f"[GSHEET] Credentials fayli topilmadi: {self.credentials_path}")
            return

        try:
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
            creds = Credentials.from_service_account_file(self.credentials_path, scopes=scopes)
            self.client = gspread.authorize(creds)
            
            client_obj = self.client
            if self.spreadsheet_id and client_obj is not None:
                try:
                    spreadsheet_obj = client_obj.open_by_key(self.spreadsheet_id)
                    if spreadsheet_obj is not None:
                        self.spreadsheet = spreadsheet_obj
                        self.sheet = spreadsheet_obj.get_worksheet(0) # Birinchi varoq
                        logger.info(f"[GSHEET OK] Google Sheets ulandi: {spreadsheet_obj.title}")
                except Exception as e:
                    logger.error(f"[GSHEET ERROR] Spreadsheet ochilmadi: {e}")
            else:
                logger.warning("[GSHEET] GSHEET_ID belgilanmagan yoki client ulanmadi")
        except Exception as e:
            logger.error(f"[GSHEET] Avtorizatsiyada xato: {e}")

    def sync_user(self, user_id, full_name, username, phone=None, business_type=None, region=None, brand_name=None, service_type=None, deadline=None):
        """Foydalanuvchi ma'lumotlarini sheetga qo'shish yoki yangilash."""
        sheet_obj = self.sheet
        if sheet_obj is None:
            logger.warning("[GSHEET] Sheet ulanmagan, sync_user bajarilmadi.")
            return
        
        try:
            # User_id bo'yicha qidirish (A ustun)
            user_id_str = str(user_id)
            cells = sheet_obj.findall(user_id_str, in_column=1)
            phone_str = str(phone) if phone else ""
            username_str = f"@{username}" if username else ""
            
            # Additional info
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            data_row = [
                full_name, 
                username_str, 
                phone_str, 
                "Active", 
                business_type or "", 
                region or "", 
                brand_name or "", 
                service_type or "", 
                deadline or "",
                now_str
            ]
            
            if cells:
                # Yangilash (B: Name, C: Username, D: Phone, E: Status, F: Business, G: Region, H: Brand, I: Service, J: Deadline, K: Last Updated)
                row_val = cells[0].row
                if row_val:
                    row = int(row_val)
                    sheet_obj.update(f"B{row}:K{row}", [data_row])
            else:
                # Yangi qo'shish (A: ID, B: Name, C: Username, D: Phone, E: Status, F: Business, G: Region, H: Brand, I: Service, J: Deadline, K: Last Updated)
                sheet_obj.append_row([user_id_str] + data_row)
        except Exception as e:
            logger.error(f"[GSHEET] sync_user error: {e}")

    def log_message(self, user_id, message, is_ai=False):
        """Xabarni logs varog'iga qo'shish."""
        ss_obj = self.spreadsheet
        if ss_obj is None:
            return
        
        try:
            # Logs varog'ini topish yoki yaratish
            if self.log_sheet is None:
                try:
                    self.log_sheet = ss_obj.worksheet("Logs")
                except gspread.exceptions.WorksheetNotFound:
                    self.log_sheet = ss_obj.add_worksheet(title="Logs", rows="1000", cols="5")
                    ls_obj = self.log_sheet
                    if ls_obj is not None:
                        ls_obj.append_row(["Time", "User ID", "Sender", "Message"])
                except Exception as ex:
                    logger.error(f"[GSHEET ERROR] Logs worksheet yaratishda xato: {ex}")
                    return

            log_sh = self.log_sheet
            if log_sh is None:
                return

            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sender = "AI" if is_ai else "User"
            msg_str = str(message or "")
            # Truncate for safety
            msg_peek = msg_str[0:5000]  # type: ignore
            log_sh.append_row([now, str(user_id), sender, msg_peek]) # type: ignore
        except Exception as e:
            logger.error(f"[GSHEET] log_message error: {e}")
            self.log_sheet = None

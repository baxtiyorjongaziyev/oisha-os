import os
import logging
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import pickle

logger = logging.getLogger(__name__)


class GoogleContactsSync:
    def __init__(self, credentials_path="service_account.json"):
        self.credentials_path = credentials_path
        self.service = None
        self.scopes = [
            "https://www.googleapis.com/auth/contacts",
            "https://www.googleapis.com/auth/directory.readonly",
        ]
        self._authenticate()

    def _authenticate(self):
        """Google API bilan avtorizatsiya (Token yoki Service Account)."""
        creds = None
        # 1. token.json - Shaxsiy akkaunt (OAuth2)
        if os.path.exists("token.pickle"):
            try:
                with open("token.pickle", "rb") as token:
                    creds = pickle.load(token)
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                    with open("token.pickle", "wb") as token:
                        pickle.dump(creds, token)
                logger.info(
                    "[GCONTACTS OK] Shaxsiy Google akkaunti (Token) ishga tushdi."
                )
            except Exception as e:
                logger.error(f"[GCONTACTS] Token yangilashda xato: {e}")
                creds = None

        # 2. service_account.json (Fallback)
        if not creds:
            if os.path.exists(self.credentials_path):
                try:
                    creds = ServiceAccountCredentials.from_service_account_file(
                        self.credentials_path, scopes=self.scopes
                    )
                    logger.info("[GCONTACTS OK] Service Account ulandi.")
                except Exception as e:
                    logger.error(
                        f"[GCONTACTS] Service Account avtorizatsiyasida xato: {e}"
                    )
            else:
                logger.warning("[GCONTACTS] Avtorizatsiya fayli topilmadi.")

        if creds:
            self.service = build("people", "v1", credentials=creds)
        else:
            logger.error("[GCONTACTS] Avtorizatsiya muvaffaqiyatsiz tugadi.")

    def get_or_create_group(
        self, group_name: str, create_if_missing: bool = True
    ) -> str:
        """Belgilangan nomli guruh (Label) yaratadi yoki bor bo'lsa ID (resourceName) sini qaytaradi."""
        if not self.service:
            return None
        try:
            # 1. Barcha guruhlarni qidirish (Pagination bilan)
            next_page_token = None
            while True:
                results = (
                    self.service.contactGroups()
                    .list(pageToken=next_page_token, pageSize=1000)
                    .execute()
                )
                groups = results.get("contactGroups", [])

                for group in groups:
                    if group.get("name") == group_name:
                        logger.info(f"[GCONTACTS] Mavjud guruh topildi: {group_name}")
                        return group.get("resourceName")

                next_page_token = results.get("nextPageToken")
                if not next_page_token:
                    break

            # 2. Agar mavjud bo'lmasa va ruxsat bo'lsa, yaratamiz
            if create_if_missing:
                logger.info(f"[GCONTACTS] Yangi guruh yaratilmoqda: {group_name}")
                new_group = (
                    self.service.contactGroups()
                    .create(body={"contactGroup": {"name": group_name}})
                    .execute()
                )
                return new_group.get("resourceName")
            else:
                logger.warning(
                    f"[GCONTACTS] Guruh topilmadi va yaratish taqiqlandi: {group_name}"
                )
                return None
        except Exception as e:
            logger.error(f"[GCONTACTS ERROR] Guruh olish/yaratishda xato: {e}")
            return None

    def create_contact(
        self, first_name, last_name="", phones=None, note="", group_name=None
    ):
        """Yangi kontakt yaratish (Bir nechta raqam va Label bilan)."""
        if not self.service:
            logger.error("[GCONTACTS] Service ulanmagan.")
            return False

        try:
            # Prepare phone numbers array
            phone_entries = []
            if phones:
                if isinstance(phones, str):
                    phones = [phones]
                for i, p in enumerate(phones):
                    phone_entries.append(
                        {"value": p, "type": "mobile" if i == 0 else "work"}
                    )

            contact_body = {
                "names": [{"givenName": first_name, "familyName": last_name}],
                "phoneNumbers": phone_entries,
                "biographies": (
                    [{"value": note, "contentType": "TEXT_PLAIN"}] if note else []
                ),
            }

            # Agar guruh berilgan bo'lsa, unga biriktiramiz
            if group_name:
                # 'Tez Natija' vazifasi uchun yangi label ochmaslik (create_if_missing=False)
                create_new = "TEZ NATIJA" not in group_name.upper()
                group_resource_name = self.get_or_create_group(
                    group_name, create_if_missing=create_new
                )
                if group_resource_name:
                    contact_body["memberships"] = [
                        {
                            "contactGroupMembership": {
                                "contactGroupResourceName": group_resource_name
                            }
                        }
                    ]

            self.service.people().createContact(body=contact_body).execute()
            logger.info(
                f"[GCONTACTS OK] Kontakt yaratildi: {first_name} {last_name} ({len(phone_entries)} ta raqam)"
            )
            return True
        except Exception as e:
            logger.error(f"[GCONTACTS ERROR] Kontakt yaratishda xato: {e}")
            return False


if __name__ == "__main__":
    # Test qilish
    logging.basicConfig(level=logging.INFO)
    sync = GoogleContactsSync()
    if sync.service:
        sync.create_contact("Test", "User", "+998901234567", "Test note from AI")

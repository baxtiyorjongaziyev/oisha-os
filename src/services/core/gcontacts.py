import os
import logging

from src.services.core.google_oauth import load_user_credentials

try:
    from google.oauth2.service_account import Credentials as ServiceAccountCredentials
    from googleapiclient.discovery import build
except ImportError:
    ServiceAccountCredentials = None
    build = None

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
        """Google API bilan avtorizatsiya (JSON token yoki Service Account)."""
        creds = None
        for token_path in ("token.json", "data/token.json"):
            creds = load_user_credentials(token_path, self.scopes)
            if creds:
                logger.info("[GCONTACTS OK] Shaxsiy Google akkaunti (Token) ishga tushdi.")
                break

        # 2. service_account.json (Fallback)
        if not creds:
            candidates = [
                self.credentials_path,
                "service_account.json",
                "data/service_account.json",
                os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip(),
            ]
            sa_path = next((p for p in dict.fromkeys(candidates) if p and os.path.exists(p)), None)
            if sa_path:
                try:
                    creds = ServiceAccountCredentials.from_service_account_file(
                        sa_path, scopes=self.scopes
                    )
                    logger.info("[GCONTACTS OK] Service Account ulandi (%s).", sa_path)
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

    def list_all_contacts(self, raise_on_error: bool = False) -> list[dict]:
        """Fetch all contacts from Google Contacts using People API."""
        if not self.service:
            logger.error("[GCONTACTS] Service ulanmagan.")
            return []

        contacts_list = []
        try:
            next_page_token = None
            while True:
                results = (
                    self.service.people()
                    .connections()
                    .list(
                        resourceName="people/me",
                        pageSize=1000,
                        pageToken=next_page_token,
                        personFields="names,phoneNumbers,biographies",
                    )
                    .execute()
                )
                connections = results.get("connections", [])
                for person in connections:
                    # Extract name
                    names = person.get("names", [])
                    display_name = names[0].get("displayName", "") if names else ""
                    given_name = names[0].get("givenName", "") if names else ""
                    family_name = names[0].get("familyName", "") if names else ""

                    # Extract phones
                    phones = []
                    for phone in person.get("phoneNumbers", []):
                        val = phone.get("value")
                        if val:
                            phones.append(val)

                    # Extract notes/biography
                    biographies = person.get("biographies", [])
                    note = biographies[0].get("value", "") if biographies else ""

                    resource_name = person.get("resourceName", "")

                    contacts_list.append({
                        "resource_name": resource_name,
                        "display_name": display_name,
                        "given_name": given_name,
                        "family_name": family_name,
                        "phones": phones,
                        "note": note,
                    })

                next_page_token = results.get("nextPageToken")
                if not next_page_token:
                    break

            logger.info(f"[GCONTACTS] Loaded {len(contacts_list)} contacts.")
            return contacts_list
        except Exception as e:
            logger.error(f"[GCONTACTS ERROR] list_all_contacts failed: {e}")
            if raise_on_error:
                raise
            return []

    def update_contact_note(self, resource_name: str, new_note: str) -> bool:
        """Update/Append note to an existing Google Contact."""
        if not self.service:
            logger.error("[GCONTACTS] Service ulanmagan.")
            return False

        try:
            # 1. Fetch current contact to get their etag (required for update)
            contact = (
                self.service.people()
                .get(resourceName=resource_name, personFields="names,phoneNumbers,biographies")
                .execute()
            )
            etag = contact.get("etag")

            # Update/replace the biography field
            contact["biographies"] = [{"value": new_note, "contentType": "TEXT_PLAIN"}]

            # 2. Update contact
            self.service.people().updateContact(
                resourceName=resource_name,
                updatePersonFields="biographies",
                body={"etag": etag, "biographies": contact["biographies"]},
            ).execute()
            logger.info(f"[GCONTACTS] Updated note for contact {resource_name}")
            return True
        except Exception as e:
            logger.error(f"[GCONTACTS ERROR] Update note failed for {resource_name}: {e}")
            return False

    def create_person(self, first_name, last_name="", phones=None, labels=None):
        """Kontakt yaratadi va resourceName qaytaradi (label yoʻq boʻlsa ochiladi)."""
        if not self.service:
            return None
        body = {
            "names": [{"givenName": first_name, "familyName": last_name}],
            "phoneNumbers": [{"value": p, "type": "mobile"} for p in (phones or [])],
        }
        try:
            res = self.service.people().createContact(body=body).execute()
        except Exception as e:
            logger.error(f"[GCONTACTS ERROR] create_person: {e}")
            return None
        resource = res.get("resourceName")
        for label in labels or []:
            self.add_to_group(resource, label)
        return resource

    def update_person(self, resource_name, first_name, last_name="", phones=None) -> bool:
        """Ismni yangilaydi, telefonni QÖSHADI (mavjudlari öchirilmaydi)."""
        if not self.service:
            return False
        try:
            cur = (
                self.service.people()
                .get(resourceName=resource_name, personFields="names,phoneNumbers")
                .execute()
            )
            body, fields = {"etag": cur.get("etag")}, []
            name = dict((cur.get("names") or [{}])[0])
            if (name.get("givenName", ""), name.get("familyName", "")) != (first_name, last_name):
                for k in ("displayName", "displayNameLastFirst", "unstructuredName", "metadata"):
                    name.pop(k, None)
                name.update(givenName=first_name, familyName=last_name)
                body["names"], fields = [name], ["names"]
            existing = cur.get("phoneNumbers") or []
            have = {"".join(ch for ch in x.get("value", "") if ch.isdigit())[-9:] for x in existing}
            new = [p for p in phones or [] if "".join(ch for ch in p if ch.isdigit())[-9:] not in have]
            if new:
                keep = [{"value": x["value"], "type": x.get("type", "mobile")} for x in existing]
                body["phoneNumbers"] = keep + [{"value": p, "type": "mobile"} for p in new]
                fields.append("phoneNumbers")
            if not fields:
                return True
            self.service.people().updateContact(
                resourceName=resource_name, updatePersonFields=",".join(fields), body=body
            ).execute()
            return True
        except Exception as e:
            logger.error(f"[GCONTACTS ERROR] update_person {resource_name}: {e}")
            return False

    def add_to_group(self, resource_name, group_name, create_if_missing=True) -> bool:
        """Kontaktni labelga qöshadi."""
        if not self.service or not resource_name:
            return False
        group = self.get_or_create_group(group_name, create_if_missing=create_if_missing)
        if not group:
            return False
        try:
            self.service.contactGroups().members().modify(
                resourceName=group, body={"resourceNamesToAdd": [resource_name]}
            ).execute()
            return True
        except Exception as e:
            logger.error(f"[GCONTACTS ERROR] add_to_group {group_name}: {e}")
            return False


if __name__ == "__main__":
    # Test qilish
    logging.basicConfig(level=logging.INFO)
    sync = GoogleContactsSync()
    if sync.service:
        sync.create_contact("Test", "User", "+998901234567", "Test note from AI")

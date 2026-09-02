import asyncio
import time
import requests  # type: ignore
from typing import Optional, Dict, Any, List
from functools import wraps

import structlog

logger = structlog.get_logger()


def retry_with_backoff(
    max_retries=3,
    initial_delay=1,
    backoff_factor=2,
    exceptions=(requests.RequestException,),
):
    """Decorator to retry API calls with exponential backoff."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    logger.warning(
                        f"[AMOCRM RETRY] {func.__name__} attempt {attempt + 1}/{max_retries} failed: {e}"
                    )
                    if attempt < max_retries - 1:
                        time.sleep(delay)
                        delay *= backoff_factor

            logger.error(
                f"[AMOCRM RETRY] {func.__name__} failed after {max_retries} attempts: {last_exception}"
            )
            raise last_exception

        return wrapper

    return decorator


def _plain_secret(value: Any) -> Any:
    """Pydantic SecretStr'ni oddiy matnga aylantiradi.

    OAuth so'rovlari client_secret'ni JSON yoki form body'da yuboradi.
    SecretStr obyekti JSON-serializable emas, form-encoding'da esa
    '**********' ko'rinishida maskalanadi — ikkala holatda ham auth jim
    yiqiladi. Chaqiruvchilarning bir qismi settings'dan xom SecretStr uzatadi,
    shuning uchun normallashtirishni shu yerda, bitta joyda qilamiz.
    """
    getter = getattr(value, "get_secret_value", None)
    return getter() if callable(getter) else value



class AmoCRMTasksNotesMixin:
    async def create_task(
        self,
        element_id: int,
        text: str,
        complete_till: int,
        responsible_user_id: Optional[int] = None,
    ):
        """Lid uchun vazifa yaratish."""
        if not self.access_token:
            self._load_token()

        lead = await self.get_lead(int(element_id))
        if not lead:
            self.last_error = "lead_state_unavailable_for_tasks"
            logger.warning(
                "[AMOCRM TASK BLOCKED] Lead %s holatini tekshirib bo'lmadi.",
                element_id,
            )
            return False

        try:
            status_id = int(lead.get("status_id") or 0)
        except (TypeError, ValueError):
            status_id = 0
        if status_id <= 0:
            self.last_error = "lead_state_unavailable_for_tasks"
            logger.warning(
                "[AMOCRM TASK BLOCKED] Lead %s statusi aniqlanmadi.",
                element_id,
            )
            return False
        if status_id in self.CLOSED_LEAD_STATUS_IDS:
            self.last_error = "lead_closed_for_tasks"
            logger.info(
                "[AMOCRM TASK BLOCKED] Yopilgan lead %s uchun vazifa yaratilmadi (status_id=%s).",
                element_id,
                status_id,
            )
            return False

        url = f"{self.base_url}/api/v4/tasks"
        task_payload = {
            "task_type_id": 1,  # Call or generic task
            "text": text,
            "complete_till": complete_till,
            "entity_id": element_id,
            "entity_type": "leads",
        }
        if responsible_user_id:
            task_payload["responsible_user_id"] = int(responsible_user_id)

        data = [task_payload]

        try:
            response = await self._request_with_auth(requests.post, url, json=data, timeout=30)
            if response.status_code == 401 and await asyncio.to_thread(self.refresh_token):
                response = await self._request_with_auth(requests.post, url, json=data, timeout=30)
            if response.status_code in [200, 201]:
                self.last_error = None
                logger.info(f"[AMOCRM OK] Vazifa yaratildi: {element_id}")
                return response.json()
            self.last_error = f"create_task_http_{response.status_code}"
            return False
        except Exception as e:
            self.last_error = "create_task_exception"
            logger.error(f"[AMOCRM TASK ERROR] {e}")
            return False

    async def get_tasks(self, is_completed: bool = False) -> List[Dict[str, Any]]:
        """AmoCRM dan vazifalarni olish."""
        if not self.access_token:
            self._load_token()

        url = f"{self.base_url}/api/v4/tasks"
        params = {"filter[is_completed]": 1 if is_completed else 0}

        try:
            response = requests.get(url, headers=self._get_headers(), params=params, timeout=30)
            if response.status_code == 200:
                data = response.json()
                return data.get("_embedded", {}).get("tasks", [])
            return []
        except Exception as e:
            logger.error(f"[AMOCRM GET TASKS ERROR] {e}")
            return []

    async def get_task(self, task_id: int) -> Optional[Dict[str, Any]]:
        """AmoCRM dan bitta vazifani ID bo'yicha olish."""
        if not self.access_token:
            self._load_token()

        url = f"{self.base_url}/api/v4/tasks/{task_id}"
        try:
            response = requests.get(url, headers=self._get_headers(), timeout=15)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.error(f"[AMOCRM GET TASK ERROR] {e}")
            return None

    async def get_lead_open_tasks(self, lead_id: int) -> List[Dict[str, Any]]:
        """Berilgan lead uchun ochiq (bajarilmagan) vazifalarni qaytaradi."""
        if not self.access_token:
            self._load_token()

        url = f"{self.base_url}/api/v4/tasks"
        params = {
            "filter[is_completed]": 0,
            "filter[entity_type]": "leads",
            "filter[entity_id]": lead_id,
        }
        try:
            response = requests.get(url, headers=self._get_headers(), params=params, timeout=30)
            if response.status_code == 200:
                return response.json().get("_embedded", {}).get("tasks", [])
            return []
        except Exception as e:
            logger.error(f"[AMOCRM GET LEAD TASKS ERROR] lead={lead_id}: {e}")
            return []

    async def create_meeting_task_for_phone(
        self,
        phone: str,
        task_text: str,
        complete_till: int,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Telefon mavjud ochiq sdelkaga tegishli bo'lsa, uchrashuv task yaratadi."""
        lead = self.find_active_lead_by_phone(phone)
        if not lead:
            return {
                "success": False,
                "reason": "active_lead_not_found",
                "lead_id": None,
            }

        lead_id = int(lead["id"])
        task = await self.create_task(
            element_id=lead_id,
            text=task_text,
            complete_till=int(complete_till),
            responsible_user_id=lead.get("responsible_user_id"),
        )
        if task and note:
            self.add_lead_note(lead_id, note)

        return {
            "success": bool(task),
            "reason": None if task else (self.last_error or "task_create_failed"),
            "lead_id": lead_id,
            "task": task,
        }

    def add_contact_note(self, contact_id: int, text: str):
        """Kontaktga izoh (primicheniya) qo'shish."""
        return self._add_note(entity_type="contacts", entity_id=contact_id, text=text)

    def add_lead_note(self, lead_id: int, text: str):
        """Bitimga (Lead) izoh qo'shish."""
        return self._add_note(entity_type="leads", entity_id=lead_id, text=text)

    def _add_note(self, entity_type: str, entity_id: int, text: str):
        """Umumiy izoh qo'shish logikasi (Internal)."""
        self._load_token()
        url = f"{self.base_url}/api/v4/{entity_type}/{entity_id}/notes"
        data = [{"note_type": "common", "params": {"text": text}}]

        try:
            response = requests.post(url, headers=self._get_headers(), json=data, timeout=30)
            if response.status_code == 401 and self.refresh_token():
                response = requests.post(url, headers=self._get_headers(), json=data, timeout=30)
            if response.status_code in [200, 201]:
                self.last_error = None
                logger.info(f"[AMOCRM OK] {entity_type} {entity_id} ga izoh qo'shildi.")
                return response.json()
            else:
                self.last_error = f"add_note_http_{response.status_code}"
                logger.error(
                    f"[AMOCRM NOTE ERROR] {response.status_code}: {response.text}"
                )
                return False
        except Exception as e:
            self.last_error = "add_note_exception"
            logger.error(f"[AMOCRM NOTE EXCEPTION] {e}")
            return False

    async def get_lead_notes(self, lead_id: int) -> List[Dict[str, Any]]:
        """Bitim (Lead) ga tegishli barcha izohlarni (notes) olish."""
        return await self.get_notes("leads", entity_id=lead_id)

    async def get_notes(
        self,
        entity_type: str,
        *,
        entity_id: Optional[int] = None,
        note_types: Optional[List[str]] = None,
        limit: int = 250,
    ) -> List[Dict[str, Any]]:
        """Read entity notes without blocking the shared Telegram/API event loop."""
        self._load_token()
        entity_path = f"/{int(entity_id)}" if entity_id is not None else ""
        url = f"{self.base_url}/api/v4/{entity_type}{entity_path}/notes"
        params: List[tuple[str, Any]] = [
            ("limit", min(max(int(limit), 1), 250)),
            ("order[updated_at]", "desc"),
        ]
        for note_type in note_types or []:
            params.append(("filter[note_type][]", note_type))
        try:
            notes: List[Dict[str, Any]] = []
            page = 1
            while page <= 20:
                page_params = [*params, ("page", page)]
                response = await self._request_with_auth(
                    requests.get, url, params=page_params, timeout=30
                )
                if response.status_code == 401:
                    if await asyncio.to_thread(self.refresh_token):
                        response = await self._request_with_auth(
                            requests.get, url, params=page_params, timeout=30
                        )
                    else:
                        self.last_error = "amocrm_unauthorized"
                        return []
                if response.status_code == 204:
                    break
                if response.status_code != 200:
                    if response.status_code == 401:
                        self.last_error = "amocrm_unauthorized"
                    return []
                payload = response.json()
                page_notes = payload.get("_embedded", {}).get("notes", [])
                notes.extend(item for item in page_notes if isinstance(item, dict))
                if not payload.get("_links", {}).get("next"):
                    break
                page += 1
            self.last_error = None
            return notes
        except Exception as e:
            self.last_error = "get_notes_exception"
            logger.error(f"[AMOCRM GET NOTES ERROR] {e}")
            return []

    async def get_recent_contact_call_notes(
        self, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Return recent contact-level calls, where telephony integrations often attach audio."""
        return await self.get_notes(
            "contacts",
            note_types=["call_in", "call_out"],
            limit=limit,
        )

    async def delete_note(self, entity_type: str, entity_id: int, note_id: int):
        """Izohni o'chirish."""
        self._load_token()
        url = f"{self.base_url}/api/v4/{entity_type}/{entity_id}/notes/{note_id}"
        try:
            response = requests.delete(url, headers=self._get_headers(), timeout=30)
            return response.status_code in [200, 204]
        except Exception as e:
            logger.error(f"[AMOCRM DELETE NOTE ERROR] {e}")
            return False

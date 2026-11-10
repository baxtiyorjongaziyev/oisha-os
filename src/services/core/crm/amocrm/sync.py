import logging
import asyncio
from typing import Any, Optional, Dict

logger = logging.getLogger(__name__)

def retry_with_backoff(retries=3, backoff_in_seconds=1):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            x = 0
            while True:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if x == retries:
                        raise e
                    sleep = (backoff_in_seconds * 2 ** x)
                    logger.warning(f"[AMOCRM_RETRY] {func.__name__} xatosi: {e}. {sleep}s kutilmoqda...")
                    await asyncio.sleep(sleep)
                    x += 1
        return wrapper
    return decorator

def _plain_secret(val: Any) -> str:
    if hasattr(val, "get_secret_value"):
        return str(val.get_secret_value())
    return str(val) if val is not None else ""

from src.services.core.crm.amocrm.auth import AmoCRMAuthMixin
from src.services.core.crm.amocrm.leads import AmoCRMLeadsMixin
from src.services.core.crm.amocrm.contacts import AmoCRMContactsMixin
from src.services.core.crm.amocrm.tasks_notes import AmoCRMTasksNotesMixin
from src.services.core.crm.amocrm.files_reports import AmoCRMFilesReportsMixin

class AmoCRMSync(
    AmoCRMAuthMixin,
    AmoCRMLeadsMixin,
    AmoCRMContactsMixin,
    AmoCRMTasksNotesMixin,
    AmoCRMFilesReportsMixin,
):
    """
    AmoCRM integratsiyasining markaziy klassi.
    Barcha modulli mixinlarni birlashtiradi.
    """
    CLOSED_LEAD_STATUS_IDS = frozenset({142, 143})

    def __init__(
        self,
        subdomain: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[Any] = None,
        redirect_url: Optional[str] = None,
        token_file: str = "data/amocrm_token.json",
    ):
        from src.settings import settings

        sub = subdomain or getattr(settings, "AMOCRM_SUBDOMAIN", "") or "jonbranding"
        self.subdomain = str(sub).strip().strip("'\"") or "jonbranding"
        raw_client_id = client_id or getattr(settings, "AMOCRM_CLIENT_ID", "")
        self.client_id = str(raw_client_id).strip().strip("'\"")
        self.client_secret = _plain_secret(
            client_secret
            if client_secret is not None
            else getattr(settings, "AMOCRM_CLIENT_SECRET", "")
        )
        raw_redirect = redirect_url or getattr(settings, "AMOCRM_REDIRECT_URL", "")
        self.redirect_url = str(raw_redirect).strip().strip("'\"")
        self.token_file = token_file
        self.base_url = f"https://{self.subdomain}.amocrm.ru"
        self.access_token: Optional[str] = None
        self.token_data: Dict[str, Any] = {}
        self.last_error: Optional[str] = None
        self.auth_blocked_until: float = 0.0
        self.auth_block_reason: Optional[str] = None
        self._contact_details_cache: Dict[int, tuple[float, Dict[str, Any]]] = {}
        
        # Security: Masked log for safety
        logger.info(f"[AMOCRM INIT] Subdomain: {subdomain}")
        self._load_token()

    @property
    def resolver(self):
        """Dynamic pipeline and custom field resolver."""
        from src.services.core.crm.amocrm_resolver import AmoPipelineResolver

        if not hasattr(self, "_resolver") or self._resolver is None:
            self._resolver = AmoPipelineResolver(amocrm=self)
        return self._resolver

    def resolve_pipeline_id(self, name_or_alias: str) -> Optional[int]:
        self.resolver.load_sync()
        return self.resolver.get_pipeline_id(name_or_alias)

    def resolve_status_id(self, pipeline: Any, status_name: str) -> Optional[int]:
        self.resolver.load_sync()
        return self.resolver.get_status_id(pipeline, status_name)

    def resolve_custom_field_id(self, field_name: str) -> Optional[int]:
        self.resolver.load_sync()
        return self.resolver.get_custom_field_id(field_name)

    def resolve_custom_field_enum_id(self, field_name: str, enum_value: str) -> Optional[int]:
        self.resolver.load_sync()
        return self.resolver.get_custom_field_enum_id(field_name, enum_value)

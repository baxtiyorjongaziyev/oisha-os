import logging
from src.services.call_analytics.helpers import *
from src.services.call_analytics.transcriber import CallTranscriberMixin
from src.services.call_analytics.scorer import CallScorerMixin
from src.services.call_analytics.normalizer import CallNormalizerMixin
from src.services.call_analytics.crm_notes import CallCrmNotesMixin
from src.services.call_analytics.crm_tasks import CallCrmTasksMixin
from src.services.call_analytics.runner import CallRunnerMixin
from src.services.call_analytics.backfill import CallBackfillMixin

logger = logging.getLogger(__name__)

class CallAnalyzer(
    CallRunnerMixin,
    CallBackfillMixin,
    CallTranscriberMixin,
    CallScorerMixin,
    CallNormalizerMixin,
    CallCrmNotesMixin,
    CallCrmTasksMixin,
):
    """
    Qo'ng'iroqlarni tahlil qilish va CRM ga sinxronizatsiya qilish markaziy xizmati.
    """
    _gemini_blocked_until: float = 0.0
    _GEMINI_COOLDOWN_KEY: str = "call_analyzer:gemini_blocked_until"
    _BACKFILL_PAGE_KEY: str = "call_analyzer:backfill_next_page"
    _BACKFILL_DONE_KEY: str = "call_analyzer:backfill_completed_at"

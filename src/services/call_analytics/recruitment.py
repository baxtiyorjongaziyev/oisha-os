"""Ishga nomzod (HR) qöngʻiroqlarini savdo suhbatlaridan ajratish."""
import inspect
import logging
import re
from typing import Any, Dict

from src.services.core.crm.amocrm_pipeline_config import HR_PIPELINE_ID

logger = logging.getLogger(__name__)

HR_SCREENING_STATUS_ID = 86197554  # Vacancy -> "Dastlabki saralash"


async def _maybe_await(value: Any) -> Any:
    return await value if inspect.isawaitable(value) else value

# Faqat butun söz sifatida. Savdo matnida uchraydigan umumiy iboralar
# ("taklif", "ish") ataylab kiritilmagan.
_RECRUITMENT_PATTERN = re.compile(
    r"\bhead\s*hunter\b|\bhh\.uz\b|\bvakansiya\w*|\brezyume\w*|\brezume\w*|"
    r"\bрезюме|\bвакансия|\bnomzod\w*|"
    r"\bishga\s+(?:kirish|qabul|joylash|ariza)\w*|\bсобеседовани|\bинтервью|\bintervyu\w*",
    re.IGNORECASE,
)


def is_recruitment_call(summary: Any) -> bool:
    """Xulosada ishga qabul belgisi aniq bormi (kalit söz topildi)."""
    return bool(_RECRUITMENT_PATTERN.search(str(summary or "")))


async def move_candidate_to_hr(amocrm: Any, lead_id: int, analysis: Dict[str, Any]) -> bool:
    """Nomzod qöngʻiroqi bölsa lidni "Vacancy (HR / Ishga Qabul)" voronkasiga
    ("Dastlabki saralash") ötkazadi. Allaqachon HR voronkasida bölsa tegmaydi."""
    if not analysis.get("hr_nomzod") or amocrm is None or not lead_id:
        return False
    try:
        lead = await _maybe_await(amocrm.get_lead(int(lead_id)))
        if lead and int(lead.get("pipeline_id") or 0) == HR_PIPELINE_ID:
            return False
        ok = await _maybe_await(amocrm.update_lead_status(
            int(lead_id), HR_SCREENING_STATUS_ID, pipeline_id=HR_PIPELINE_ID,
        ))
        logger.info("[CALL-HR] lead %s -> HR voronka: %s", lead_id, ok)
        return bool(ok)
    except Exception as exc:  # noqa: BLE001 — pipelineni himoya qilish
        logger.error("[CALL-HR] lead %s kochirilmadi: %s", lead_id, exc)
        return False


async def route_call_crm(
    db: Any, amocrm: Any, lead_id: int, analysis: Dict[str, Any],
    responsible_user_id: Any = None,
) -> None:
    """Nomzod -> HR voronka; aks holda odatiy savdo CRM avtomatikasi."""
    if analysis.get("hr_nomzod"):
        await move_candidate_to_hr(amocrm, lead_id, analysis)
        return
    from src.services.call_analytics.crm_automation_hook import run_crm_automation
    await run_crm_automation(db, amocrm, lead_id, analysis, responsible_user_id)


def apply_recruitment_override(category: str, summary: Any) -> str:
    """AI "Mijoz" desa ham, xulosada ishga qabul belgilari bölsa "Jamoa"."""
    if category != "Mijoz":
        return category
    if _RECRUITMENT_PATTERN.search(str(summary or "")):
        return "Jamoa"
    return category

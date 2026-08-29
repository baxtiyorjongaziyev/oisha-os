import datetime
import os
import logging
from html import escape
from typing import Any, Dict, List, Optional
from src.time_utils import get_local_now
from src.services.core.agent_loop import AgentTask, AgentTaskResult, MinimalAgentLoop
from src.services.core.agent_policy import AgentPolicyEngine
from src.services.core.agent_verifier import NotificationOutcomeVerifier
from src.services.core.persona_hub import get_persona
from src.services.core.crm.amocrm_pipeline_config import LEGACY_CLOSER_PIPELINE_ID
from src.database import Database
from src.agents.researcher_agent import ResearcherAgent
from src import config

logger = logging.getLogger(__name__)

DAILY_PLAN_PHASES: Dict[str, Dict[str, str]] = {
    "initial": {
        "job": "daily_plan_initial",
        "title": "📝 <b>Kunlik plan (Internal PM Audit)</b>",
        "deadline": "11:30",
        "tone": "Loyiha bo'yicha bugungi aniq delivery-planingizni topshiring. Hech bir loyiha stagnatsiyada qolmasligi shart.",
    },
    "reminder": {
        "job": "daily_plan_reminder",
        "title": "⏰ <b>PM Audit: Plan hanuz yo'q</b>",
        "deadline": "14:00",
        "tone": "Loyiha bosqichlari bo'yicha kechikish xavfi bor. Plan topshirish intizomini ta'minlang.",
    },
    "escalation": {
        "job": "daily_plan_escalation",
        "title": "🚨 <b>Operatsion eskalatsiya (Strict COO)</b>",
        "deadline": "Darhol",
        "tone": "Audit natijasida intizom buzilishi aniqlandi. Loyihalar xavf ostida. PM darhol hisobot bersin.",
    },
}

PM_STAGE_HINTS = [
    (
        ("brief", "brif"),
        ("Konsept / yo'nalish", "Brifni yopib, kreativ yo'nalishni tasdiqlang."),
    ),
    (
        ("strategy", "strategiya", "research", "tahlil"),
        ("Naming / copy", "Research deliverable'ni yakunlab, ijodiy blokka uzating."),
    ),
    (
        ("naming", "copy", "nom"),
        ("Design", "Tanlangan variantni dizayn ishiga topshiring."),
    ),
    (
        ("design", "dizayn", "draft", "maket"),
        (
            "Client review",
            "Mijoz feedbackini bugun oling va deadline ni qayta mahkamlang.",
        ),
    ),
    (
        ("review", "feedback", "approval", "tasdiq"),
        (
            "Revision / production",
            "Feedbackni yopib, keyingi etapni kalendarga kiriting.",
        ),
    ),
    (
        ("production", "dev", "fayl", "topshirish"),
        ("Delivery", "Topshirish paketini tayyorlab, final sanani yoping."),
    ),
]


async def generate_ai_message(user_id: int, prompt: str) -> str:
    """AI orqali dinamik va samimiy xabar yaratish."""
    api_keys = {
        "gemini": os.environ.get("GEMINI_API_KEY")
        or getattr(config, "GEMINI_API_KEY", ""),
        "groq": os.environ.get("GROQ_API_KEY", ""),
    }
    system_instruction = get_persona(is_team_member=True)
    agent = ResearcherAgent("proactive_bot", system_instruction, api_keys)
    response = await agent.process_task(user_id, prompt)
    response = response.replace("<p>", "").replace("</p>", "\n")
    response = response.replace("<br>", "\n").replace("<br/>", "\n")
    return response


def _safe_text(value: Any, fallback: str = "Noma'lum") -> str:
    text = str(value).strip() if value is not None else ""
    return text or fallback


def _mention(member: Dict[str, Any]) -> str:
    username = (member.get("username") or "").strip()
    name = escape(_safe_text(member.get("name"), f"User_{member.get('user_id', '0')}"))
    if username:
        return f"@{escape(username)}"

    user_id = member.get("user_id")
    if user_id:
        return f"<a href='tg://user?id={user_id}'>{name}</a>"
    return name


def _lead_idle_hours(lead: Dict[str, Any], now_ts: Optional[int] = None) -> int:
    now_epoch = now_ts or int(get_local_now().timestamp())
    updated_at = int(lead.get("updated_at") or 0)
    if updated_at <= 0:
        return 0
    return max(0, int((now_epoch - updated_at) / 3600))


def _format_idle_text(hours: int) -> str:
    if hours >= 48:
        return f"{hours // 24} kun"
    return f"{hours} soat"


def _sales_action_for_lead(lead: Dict[str, Any]) -> str:
    idle_hours = _lead_idle_hours(lead)
    pipeline_id = int(lead.get("pipeline_id") or 0)
    price = int(lead.get("price") or 0)

    if idle_hours >= 72:
        return "bugun qo'ng'iroq qiling, e'tirozni yozing va keyingi qaror sanasini CRMga kiriting"
    if pipeline_id == LEGACY_CLOSER_PIPELINE_ID:
        if price >= 10_000_000:
            return "qaror beruvchi va narx e'tirozini yopadigan taklif yuboring"
        return "yakunlovchi follow-up yuborib, meeting yoki to'lov sanasini aniq mahkamlang"
    return "briefni aniqlashtirib, keyingi meeting yoki КП sanasini belgilang"


def _sales_manager_playbook(leads: List[Dict[str, Any]]) -> str:
    high_value = any(int(lead.get("price") or 0) >= 10_000_000 for lead in leads)
    older_than_3d = any(_lead_idle_hours(lead) >= 72 for lead in leads)
    if older_than_3d:
        return "1) bugun qo'ng'iroq, 2) yo'qotish sababini yozish, 3) keyingi sanani CRMga kiritish"
    if high_value:
        return "1) qaror beruvchini topish, 2) qiymatni qayta asoslash, 3) taklifga deadline qo'yish"
    return "1) follow-up yuborish, 2) next stepni yozish, 3) lidni bosqichsiz qoldirmaslik"


def _project_stage_recommendation(stage_name: str) -> tuple[str, str]:
    normalized = (stage_name or "").lower()
    for keywords, recommendation in PM_STAGE_HINTS:
        if any(keyword in normalized for keyword in keywords):
            return recommendation
    return (
        "Keyingi stage aniqlansin",
        "Statusni yangilang yoki blokerni yozib, keyingi mas'ulni belgilang.",
    )


def _project_age_days(project: Dict[str, Any]) -> int:
    from src.services.core.airtable_sync import AirtableSync as _AT

    fields = project.get("fields", {})
    start_raw = _AT._get_field(fields, "start_date")
    if not start_raw:
        return 0

    try:
        created_dt = datetime.datetime.fromisoformat(
            str(start_raw).replace("Z", "+00:00")
        )
    except ValueError:
        return 0

    now = get_local_now()
    if created_dt.tzinfo is not None:
        now_cmp = now.astimezone(datetime.timezone.utc)
    else:
        now_cmp = now.replace(tzinfo=None)
    return max(0, (now_cmp - created_dt).days)


async def _run_notification_agent(
    db: Database,
    task: AgentTask,
    executor,
) -> AgentTaskResult:
    loop = MinimalAgentLoop(db)
    policy_engine = AgentPolicyEngine(db)
    verifier = NotificationOutcomeVerifier()

    decision = await policy_engine.evaluate_action(task)
    await loop.log_stage(
        task, "agent_policy", decision.to_payload(), success=decision.allowed
    )
    if not decision.allowed:
        plan = loop.plan_task(task)
        execution = {
            "task_id": task.task_id,
            "success": False,
            "reason": decision.reason,
            "policy": decision.to_payload(),
            "blocked_at": get_local_now().isoformat(),
        }
        verification = {
            "task_id": task.task_id,
            "success": False,
            "reason": decision.reason,
            "verification_mode": "policy_gate",
            "verified_at": get_local_now().isoformat(),
        }
        await loop.log_stage(task, "agent_execute", execution, success=False)
        await loop.log_stage(task, "agent_verify", verification, success=False)
        return AgentTaskResult(
            task_id=task.task_id,
            success=False,
            plan=plan,
            execution=execution,
            verification=verification,
            finished_at=get_local_now().isoformat(),
        )

    return await loop.run(task, executor, verifier.verify)

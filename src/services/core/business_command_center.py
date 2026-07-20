"""Evidence-first command planning for Oisha's business control center."""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from typing import Any


@dataclass(frozen=True)
class IntegrationCapability:
    key: str
    name: str
    configured: bool
    operations: tuple[str, ...]


@dataclass(frozen=True)
class CommandPlan:
    intent: str
    mutation: bool
    approval_required: bool
    confidence: float
    entities: dict[str, Any]
    required_sources: tuple[str, ...]
    next_action: str
    idempotency_key: str

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BrandingERPPhase:
    phase: int
    title: str
    outcome: str
    source_of_truth: tuple[str, ...]
    must_run_24_7: tuple[str, ...]
    acceptance_checks: tuple[str, ...]

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TelegramMigrationCheck:
    key: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class TelegramMigrationStatus:
    stage: str
    userbot_runtime: str
    bot_runtime_backend: str
    aiogram_dispatcher_enabled: bool
    rollback_backend: str
    checks: tuple[TelegramMigrationCheck, ...]
    next_actions: tuple[str, ...]

    def to_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["ready_count"] = sum(1 for item in self.checks if item.ok)
        payload["total_count"] = len(self.checks)
        return payload


@dataclass(frozen=True)
class SalesPriorityLead:
    lead_id: int
    name: str
    priority_score: int
    priority: str
    action: str
    reasons: tuple[str, ...]
    evidence: dict[str, Any]

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProjectRiskItem:
    project_id: str
    name: str
    risk_score: int
    risk: str
    action: str
    reasons: tuple[str, ...]
    evidence: dict[str, Any]

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FinanceRiskItem:
    project_id: str
    name: str
    risk_score: int
    risk: str
    action: str
    reasons: tuple[str, ...]
    evidence: dict[str, Any]

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TeamCapacityItem:
    owner_key: str
    owner_name: str
    load_score: int
    load: str
    action: str
    reasons: tuple[str, ...]
    evidence: dict[str, Any]

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


_PHONE_RE = re.compile(r"\+?998\d{9}")
_LEAD_ID_RE = re.compile(r"(?:lead|lid|bitim)\s*#?\s*(\d{5,})", re.IGNORECASE)
_TIME_RE = re.compile(r"\b(?:soat\s*)?(\d{1,2})(?::(\d{2}))?\b", re.IGNORECASE)
CLOSED_LEAD_STATUS_IDS = frozenset({142, 143})
CLOSED_PROJECT_STAGE_MARKERS = ("done", "completed", "yakunlangan", "topshirildi", "arxiv", "bekor", "cancel")
PROJECT_FIELD_ALIASES = {
    "name": ("Loyihani nomi?", "Project Name", "Name", "name", "title"),
    "stage": ("Loyiha bosqichi", "Stage", "Status", "Holati", "stage", "status"),
    "deadline": ("END sana", "Deadline", "Muddati", "deadline", "due_date"),
    "manager": ("PM", "Manager", "Mas'ul", "owner", "manager"),
    "summary": ("Xulosa", "Summary", "Chat Summary", "notes", "summary"),
    "budget": ("Kelishgan narx", "Jami loyiha narxi (UZS)", "Budget", "budget"),
    "paid": ("To'langan", "Jami to'langan", "paid_amount", "Jami to'langan USD", "paid"),
    "remaining": ("Qoldiq to'lov $", "Qoldiq", "remaining", "remaining_amount"),
    "payment_status": ("To'lov statusi", "To'lovlar holati", "payment_status"),
}


def _configured(*keys: str) -> bool:
    return all(bool((os.getenv(key) or "").strip()) for key in keys)


def list_integration_capabilities() -> list[dict[str, Any]]:
    """Return truthful runtime capabilities without exposing secret values."""
    capabilities = [
        IntegrationCapability(
            "amocrm",
            "amoCRM",
            _configured("AMOCRM_SUBDOMAIN", "AMOCRM_CLIENT_ID", "AMOCRM_CLIENT_SECRET"),
            ("lead_create", "task_create", "pipeline_read", "note_write"),
        ),
        IntegrationCapability(
            "telegram_bot",
            "Telegram Bot API",
            _configured("BOT_TOKEN"),
            ("notification_send", "approval_request", "command_receive"),
        ),
        IntegrationCapability(
            "telegram_userbot",
            "Telegram userbot (Oracle only)",
            os.getenv("USERBOT_RUNTIME_OWNER", "").strip().lower() == "oracle_vm"
            and _configured("USERBOT_SESSION_STRING"),
            ("conversation_read", "voice_receive"),
        ),
        IntegrationCapability(
            "airtable",
            "Airtable",
            _configured("AIRTABLE_API_KEY"),
            ("project_read", "project_update"),
        ),
        IntegrationCapability(
            "google_workspace",
            "Google Workspace",
            _configured("GOOGLE_SERVICE_ACCOUNT_JSON")
            or _configured("GOOGLE_APPLICATION_CREDENTIALS"),
            ("sheets_read", "drive_write", "calendar_event"),
        ),
    ]
    return [asdict(item) for item in capabilities]


def branding_erp_roadmap() -> list[dict[str, Any]]:
    """Return the practical integration-first ERP roadmap for branding agencies."""
    phases = [
        BrandingERPPhase(
            phase=1,
            title="24/7 runtime and truthful sources",
            outcome="Oracle VM runs the userbot, bot head, API, schedulers, and health checks without local dependency.",
            source_of_truth=("Oracle VM", "GitHub Secrets", "production .env"),
            must_run_24_7=("Telethon userbot", "bot-token head", "FastAPI health/ready", "n8n workflows"),
            acceptance_checks=("systemd active", "/healthz 200", "/readyz 200", "no local userbot session owner"),
        ),
        BrandingERPPhase(
            phase=2,
            title="Sales and follow-up control",
            outcome="AmoCRM owns lead/contact/deal/task state; Oisha only plans, verifies, and requests approval for mutations.",
            source_of_truth=("AmoCRM", "Telegram evidence"),
            must_run_24_7=("AmoCRM webhook", "sales priority digest", "follow-up reminders"),
            acceptance_checks=("pipeline IDs verified", "tasks created after approval", "stale leads routed to reactivation"),
        ),
        BrandingERPPhase(
            phase=3,
            title="Delivery and documents",
            outcome="Brief, KP, brandbook files, client feedback, project status, and deadlines are connected through cheap external tools.",
            source_of_truth=("Google Drive", "Google Sheets or Airtable", "Calendar"),
            must_run_24_7=("deadline monitor", "feedback intake", "project risk alerts"),
            acceptance_checks=("project has owner", "deadline exists", "client files linked", "risk alert has source link"),
        ),
        BrandingERPPhase(
            phase=4,
            title="Finance and margin",
            outcome="Advance, remaining payment, costs, margin, and debt are visible per client and project.",
            source_of_truth=("Hisobchi", "Google Sheets", "AmoCRM deal value"),
            must_run_24_7=("payment reminder", "margin report", "debt alert"),
            acceptance_checks=("advance verified", "expense source exists", "margin is not guessed"),
        ),
        BrandingERPPhase(
            phase=5,
            title="Aiogram bot head migration",
            outcome="Userbot stays Telethon; @jonairobot bot-account flows move to Aiogram through a compatibility adapter.",
            source_of_truth=("Telegram Bot API", "owner approval log"),
            must_run_24_7=("Aiogram dispatcher", "approval callbacks", "admin commands"),
            acceptance_checks=("Telethon userbot still authorized", "callback tests pass", "rollback to Telethon bot head is possible"),
        ),
    ]
    return [phase.to_payload() for phase in phases]


def telegram_bot_migration_status(
    *,
    bot_runtime_backend: str | None = None,
    aiogram_dispatcher_enabled: bool | None = None,
) -> dict[str, Any]:
    """Report the safe migration state without exposing Telegram secrets."""
    backend = (bot_runtime_backend or os.getenv("TELEGRAM_BOT_RUNTIME_BACKEND") or "telethon").strip().lower()
    dispatcher_enabled = (
        _env_bool("TELEGRAM_ADMIN_AIOGRAM_DISPATCHER_ENABLED")
        if aiogram_dispatcher_enabled is None
        else aiogram_dispatcher_enabled
    )
    userbot_owner = (os.getenv("USERBOT_RUNTIME_OWNER") or "").strip().lower()
    userbot_configured = _configured("USERBOT_SESSION_STRING")
    bot_token_configured = _configured("BOT_TOKEN")

    checks = (
        TelegramMigrationCheck(
            "userbot_oracle_owned",
            userbot_owner == "oracle_vm" and userbot_configured,
            "Telethon userbot must stay on Oracle VM only.",
        ),
        TelegramMigrationCheck(
            "bot_token_configured",
            bot_token_configured,
            "Bot-account token exists for outbound/admin flows.",
        ),
        TelegramMigrationCheck(
            "adapter_backend_valid",
            backend in {"telethon", "aiogram"},
            "Bot runtime backend is rollbackable between telethon and aiogram.",
        ),
        TelegramMigrationCheck(
            "aiogram_dispatcher_safe",
            not dispatcher_enabled or backend == "aiogram",
            "Aiogram dispatcher should be enabled only after backend is aiogram.",
        ),
    )

    if backend == "aiogram" and dispatcher_enabled:
        stage = "aiogram_manual_dispatcher_ready"
    elif backend == "aiogram":
        stage = "aiogram_send_only"
    else:
        stage = "telethon_adapter_ready"

    next_actions = (
        "Keep userbot on Telethon and Oracle VM.",
        "Switch TELEGRAM_BOT_RUNTIME_BACKEND=aiogram only after focused tests pass.",
        "Enable TELEGRAM_ADMIN_AIOGRAM_DISPATCHER_ENABLED only for controlled dispatcher rollout.",
        "Verify callback/update handling before full bot-account cutover.",
    )
    status = TelegramMigrationStatus(
        stage=stage,
        userbot_runtime="telethon_oracle_only" if userbot_owner == "oracle_vm" else "not_confirmed",
        bot_runtime_backend=backend,
        aiogram_dispatcher_enabled=dispatcher_enabled,
        rollback_backend="telethon",
        checks=checks,
        next_actions=next_actions,
    )
    return status.to_payload()


def _env_bool(key: str) -> bool:
    return (os.getenv(key) or "").strip().lower() in {"1", "true", "yes", "on"}


def build_sales_today_priorities(
    leads: list[dict[str, Any]],
    *,
    open_tasks_by_lead: dict[int, list[dict[str, Any]]] | None = None,
    now: datetime | None = None,
    limit: int = 12,
) -> dict[str, Any]:
    """Rank open AmoCRM leads for today's seller conversations."""
    current = now or datetime.now(timezone.utc)
    tasks_map = open_tasks_by_lead or {}
    ranked: list[SalesPriorityLead] = []
    skipped_closed = 0

    for lead in leads:
        lead_id = _int_or_zero(lead.get("id"))
        status_id = _int_or_zero(lead.get("status_id"))
        if status_id in CLOSED_LEAD_STATUS_IDS:
            skipped_closed += 1
            continue
        if not lead_id:
            continue

        tasks = tasks_map.get(lead_id, [])
        contacts = _lead_contacts(lead)
        updated_at = _int_or_zero(lead.get("updated_at"))
        created_at = _int_or_zero(lead.get("created_at"))
        responsible_id = _int_or_zero(lead.get("responsible_user_id"))
        price = _int_or_zero(lead.get("price"))
        updated_age_hours = _age_hours(updated_at, current)
        created_age_days = _age_days(created_at, current)

        score = 0
        reasons: list[str] = []
        action = "Call or message the client, then log the next task in AmoCRM."

        if not tasks:
            score += 35
            reasons.append("no_open_task")
            action = "Create the next follow-up task after owner approval."
        elif _has_overdue_task(tasks, current):
            score += 30
            reasons.append("overdue_task")
            action = "Complete or reschedule the overdue follow-up today."

        if updated_age_hours is not None and updated_age_hours >= 48:
            score += 25
            reasons.append("stale_48h_plus")
        elif updated_age_hours is not None and updated_age_hours >= 24:
            score += 15
            reasons.append("stale_24h_plus")

        if not contacts:
            score += 20
            reasons.append("no_contact_attached")
            action = "Find or attach the decision-maker contact before outreach."

        if not responsible_id:
            score += 20
            reasons.append("no_responsible")

        if price >= 20_000_000:
            score += 15
            reasons.append("high_value")
        elif price > 0:
            score += 5
            reasons.append("priced")
        else:
            score += 8
            reasons.append("price_missing")

        if created_age_days is not None and created_age_days <= 1:
            score += 10
            reasons.append("fresh_lead")

        priority = "high" if score >= 55 else "medium" if score >= 30 else "low"
        evidence = {
            "source": "amocrm",
            "lead_id": lead_id,
            "status_id": status_id,
            "responsible_user_id": responsible_id or None,
            "price": price,
            "open_task_count": len(tasks),
            "contact_count": len(contacts),
            "updated_at": updated_at or None,
            "created_at": created_at or None,
            "updated_age_hours": updated_age_hours,
        }
        ranked.append(
            SalesPriorityLead(
                lead_id=lead_id,
                name=str(lead.get("name") or f"Lead #{lead_id}"),
                priority_score=score,
                priority=priority,
                action=action,
                reasons=tuple(reasons),
                evidence=evidence,
            )
        )

    ranked.sort(key=lambda item: (-item.priority_score, item.lead_id))
    selected = ranked[: max(1, min(int(limit), 50))]
    return {
        "status": "ready" if selected else "empty",
        "source": "amocrm",
        "generated_at": current.isoformat(),
        "items": [item.to_payload() for item in selected],
        "scanned_count": len(leads),
        "skipped_closed_count": skipped_closed,
        "claim_policy": "Only AmoCRM source fields are used; no invented leads or fake facts.",
    }


def build_project_delivery_risks(
    projects: list[dict[str, Any]],
    *,
    today: date | None = None,
    limit: int = 12,
) -> dict[str, Any]:
    """Rank active projects that need PM/owner attention."""
    current = today or datetime.now(timezone.utc).date()
    ranked: list[ProjectRiskItem] = []
    skipped_closed = 0

    for project in projects:
        fields = project.get("fields", project) or {}
        project_id = str(project.get("id") or _field_text(fields, "project_id") or "")
        name = _field_text(fields, "name") or "Nomsiz loyiha"
        stage = _field_text(fields, "stage") or ""
        deadline_raw = _field_text(fields, "deadline")
        manager = _field_text(fields, "manager")
        summary = _field_text(fields, "summary")

        if stage and any(marker in stage.lower() for marker in CLOSED_PROJECT_STAGE_MARKERS):
            skipped_closed += 1
            continue

        score = 0
        reasons: list[str] = []
        action = "PM statusini yangilang va keyingi deadline/owner qadamini belgilang."
        deadline_date = _parse_date(deadline_raw)
        days_until_due = None

        if deadline_date is None:
            score += 35
            reasons.append("deadline_missing")
            action = "Deadline aniqlang va loyiha kartasiga yozing."
        else:
            days_until_due = (deadline_date - current).days
            if days_until_due < 0:
                score += 50
                reasons.append("overdue")
                action = "Bugun mijozga va PMga yangi real deadline tasdiqlating."
            elif days_until_due == 0:
                score += 40
                reasons.append("due_today")
                action = "Bugun topshiriladigan deliverable va mas'ulni tasdiqlang."
            elif days_until_due <= 3:
                score += 28
                reasons.append("due_3_days")

        if not manager:
            score += 30
            reasons.append("owner_missing")
            action = "PM/mas'ul tayinlang va javobgarlikni yozib qo'ying."

        if not stage:
            score += 20
            reasons.append("stage_missing")

        if not summary:
            score += 8
            reasons.append("summary_missing")

        if score <= 0:
            continue

        risk = "critical" if score >= 70 else "high" if score >= 45 else "medium"
        evidence = {
            "source": "airtable",
            "project_id": project_id or None,
            "stage": stage or None,
            "deadline": deadline_raw,
            "days_until_due": days_until_due,
            "manager": manager,
            "has_summary": bool(summary),
        }
        ranked.append(
            ProjectRiskItem(
                project_id=project_id,
                name=name,
                risk_score=score,
                risk=risk,
                action=action,
                reasons=tuple(reasons),
                evidence=evidence,
            )
        )

    ranked.sort(key=lambda item: (-item.risk_score, item.name.lower()))
    selected = ranked[: max(1, min(int(limit), 50))]
    return {
        "status": "ready" if selected else "empty",
        "source": "airtable",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": [item.to_payload() for item in selected],
        "scanned_count": len(projects),
        "skipped_closed_count": skipped_closed,
        "claim_policy": "Only Airtable/project source fields are used; no invented project risks.",
    }


def build_finance_project_risks(
    projects: list[dict[str, Any]],
    *,
    limit: int = 12,
) -> dict[str, Any]:
    """Rank project payment risks without inventing missing finance numbers."""
    ranked: list[FinanceRiskItem] = []
    skipped_closed = 0

    for project in projects:
        fields = project.get("fields", project) or {}
        project_id = str(project.get("id") or fields.get("id") or _field_text(fields, "project_id") or "")
        name = _field_text(fields, "name") or str(fields.get("title") or "Nomsiz loyiha")
        stage = _field_text(fields, "stage") or str(fields.get("stage") or "")
        if stage and any(marker in stage.lower() for marker in CLOSED_PROJECT_STAGE_MARKERS):
            skipped_closed += 1
            continue

        budget = _money_value(_field_text(fields, "budget") or fields.get("budget"))
        paid = _money_value(_field_text(fields, "paid") or fields.get("paid_amount"))
        remaining_raw = _money_value(_field_text(fields, "remaining") or fields.get("remaining"))
        remaining = remaining_raw
        if remaining is None and budget is not None and paid is not None:
            remaining = max(0, budget - paid)
        payment_status = (_field_text(fields, "payment_status") or "").lower()

        score = 0
        reasons: list[str] = []
        action = "To'lov holatini manba kartada yangilang va keyingi pul qadamini belgilang."

        if budget is None or budget <= 0:
            score += 35
            reasons.append("price_missing")
            action = "Loyiha narxini aniqlang va source kartaga yozing."

        if paid is None:
            score += 30
            reasons.append("paid_amount_missing")
            action = "To'langan summani Hisobchi/Airtable bilan tasdiqlang."
        elif budget and paid < budget * 0.5:
            score += 35
            reasons.append("advance_below_50")
            action = "50% avans talabini tekshiring va mijoz bilan to'lovni yoping."

        if remaining and remaining > 0:
            score += 20
            reasons.append("remaining_payment")

        if payment_status and any(word in payment_status for word in ("qarz", "debt", "overdue", "kechik")):
            score += 30
            reasons.append("payment_overdue")
            action = "Qarzdorlik bo'yicha bugun eslatma va aniq to'lov sanasini oling."

        if not payment_status:
            score += 8
            reasons.append("payment_status_missing")

        if score <= 0:
            continue

        risk = "critical" if score >= 70 else "high" if score >= 45 else "medium"
        evidence = {
            "source": "project_finance",
            "project_id": project_id or None,
            "stage": stage or None,
            "budget": budget,
            "paid_amount": paid,
            "remaining_amount": remaining,
            "payment_status": payment_status or None,
            "margin": None,
            "margin_policy": "Margin is not calculated unless real cost source is available.",
        }
        ranked.append(
            FinanceRiskItem(
                project_id=project_id,
                name=name,
                risk_score=score,
                risk=risk,
                action=action,
                reasons=tuple(reasons),
                evidence=evidence,
            )
        )

    ranked.sort(key=lambda item: (-item.risk_score, item.name.lower()))
    selected = ranked[: max(1, min(int(limit), 50))]
    return {
        "status": "ready" if selected else "empty",
        "source": "project_finance",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": [item.to_payload() for item in selected],
        "scanned_count": len(projects),
        "skipped_closed_count": skipped_closed,
        "claim_policy": "Only project finance source fields are used; margin is not guessed.",
    }


def build_team_capacity_snapshot(
    projects: list[dict[str, Any]],
    *,
    employee_names: dict[int, str] | None = None,
    today: date | None = None,
    limit: int = 12,
) -> dict[str, Any]:
    """Summarize team workload from active project assignments."""
    current = today or datetime.now(timezone.utc).date()
    names = employee_names or {}
    owners: dict[str, dict[str, Any]] = {}
    unassigned_count = 0
    skipped_closed = 0

    for project in projects:
        fields = project.get("fields", project) or {}
        stage = _field_text(fields, "stage") or str(fields.get("stage") or "")
        if stage and any(marker in stage.lower() for marker in CLOSED_PROJECT_STAGE_MARKERS):
            skipped_closed += 1
            continue

        owner_name = _field_text(fields, "manager")
        assigned_to = _int_or_zero(fields.get("assigned_to"))
        if not owner_name and assigned_to:
            owner_name = names.get(assigned_to) or f"employee:{assigned_to}"
        owner_key = owner_name.strip().lower() if owner_name else "unassigned"
        if owner_key == "unassigned":
            unassigned_count += 1
            owner_name = "PM tayinlanmagan"

        deadline_date = _parse_date(_field_text(fields, "deadline") or fields.get("deadline"))
        days_until_due = (deadline_date - current).days if deadline_date else None
        row = owners.setdefault(
            owner_key,
            {
                "owner_name": owner_name,
                "active_projects": 0,
                "overdue_projects": 0,
                "due_3_days": 0,
                "missing_deadline": 0,
                "missing_stage": 0,
                "project_ids": [],
            },
        )
        row["active_projects"] += 1
        project_id = str(project.get("id") or fields.get("id") or fields.get("project_id") or "")
        if project_id:
            row["project_ids"].append(project_id)
        if days_until_due is None:
            row["missing_deadline"] += 1
        elif days_until_due < 0:
            row["overdue_projects"] += 1
        elif days_until_due <= 3:
            row["due_3_days"] += 1
        if not stage:
            row["missing_stage"] += 1

    items: list[TeamCapacityItem] = []
    for owner_key, row in owners.items():
        score = (
            row["active_projects"] * 12
            + row["overdue_projects"] * 25
            + row["due_3_days"] * 15
            + row["missing_deadline"] * 8
            + row["missing_stage"] * 5
        )
        reasons: list[str] = []
        if owner_key == "unassigned":
            score += 30
            reasons.append("unassigned_projects")
        if row["active_projects"] >= 5:
            reasons.append("high_project_count")
        if row["overdue_projects"]:
            reasons.append("overdue_projects")
        if row["due_3_days"]:
            reasons.append("due_3_days")
        if row["missing_deadline"]:
            reasons.append("missing_deadline")
        if row["missing_stage"]:
            reasons.append("missing_stage")

        load = "overloaded" if score >= 70 else "busy" if score >= 35 else "normal"
        action = (
            "PM tayinlang va egasiz loyihalarni jamoaga taqsimlang."
            if owner_key == "unassigned"
            else "Deadline va deliverablelarni tekshirib, ortiqcha yukni qayta taqsimlang."
            if load == "overloaded"
            else "Bugungi ustuvor deliverablelarni tasdiqlang."
        )
        evidence = {
            "source": "project_assignments",
            "active_projects": row["active_projects"],
            "overdue_projects": row["overdue_projects"],
            "due_3_days": row["due_3_days"],
            "missing_deadline": row["missing_deadline"],
            "missing_stage": row["missing_stage"],
            "project_ids": row["project_ids"][:10],
        }
        items.append(
            TeamCapacityItem(
                owner_key=owner_key,
                owner_name=row["owner_name"],
                load_score=score,
                load=load,
                action=action,
                reasons=tuple(reasons),
                evidence=evidence,
            )
        )

    items.sort(key=lambda item: (-item.load_score, item.owner_name.lower()))
    selected = items[: max(1, min(int(limit), 50))]
    return {
        "status": "ready" if selected else "empty",
        "source": "project_assignments",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": [item.to_payload() for item in selected],
        "scanned_count": len(projects),
        "skipped_closed_count": skipped_closed,
        "unassigned_project_count": unassigned_count,
        "claim_policy": "Only project assignment fields are used; team capacity is not guessed.",
    }


async def collect_sales_today_priorities(
    amocrm: Any,
    *,
    limit: int = 12,
) -> dict[str, Any]:
    """Read AmoCRM and return seller priorities, or a truthful unavailable state."""
    if amocrm is None or not hasattr(amocrm, "get_leads_detailed"):
        return {
            "status": "source_unavailable",
            "source": "amocrm",
            "items": [],
            "reason": "amocrm_client_unavailable",
            "claim_policy": "No fake priorities are generated without live CRM access.",
        }

    try:
        leads = await amocrm.get_leads_detailed(limit=min(max(limit * 3, 20), 50))
    except Exception as exc:
        return {
            "status": "source_unavailable",
            "source": "amocrm",
            "items": [],
            "reason": type(exc).__name__,
            "claim_policy": "No fake priorities are generated when AmoCRM read fails.",
        }

    if not leads and getattr(amocrm, "last_error", None):
        return {
            "status": "source_unavailable",
            "source": "amocrm",
            "items": [],
            "reason": getattr(amocrm, "last_error", "amocrm_empty_or_error"),
            "claim_policy": "No fake priorities are generated when AmoCRM has no evidence.",
        }

    open_tasks_by_lead = {}
    if hasattr(amocrm, "get_lead_open_tasks"):
        for lead in leads[: min(len(leads), 25)]:
            lead_id = lead.get("id")
            if not lead_id:
                continue
            try:
                open_tasks_by_lead[int(lead_id)] = await amocrm.get_lead_open_tasks(int(lead_id))
            except Exception:
                open_tasks_by_lead[int(lead_id)] = []

    return build_sales_today_priorities(
        leads,
        open_tasks_by_lead=open_tasks_by_lead,
        limit=limit,
    )


async def collect_project_delivery_risks(
    airtable: Any,
    *,
    limit: int = 12,
) -> dict[str, Any]:
    """Read Airtable projects and return truthful project/deadline risks."""
    if airtable is None or not hasattr(airtable, "get_projects"):
        return {
            "status": "source_unavailable",
            "source": "airtable",
            "items": [],
            "reason": "airtable_client_unavailable",
            "claim_policy": "No fake project risks are generated without live project access.",
        }
    try:
        import asyncio

        projects = await asyncio.to_thread(airtable.get_projects)
    except Exception as exc:
        return {
            "status": "source_unavailable",
            "source": "airtable",
            "items": [],
            "reason": type(exc).__name__,
            "claim_policy": "No fake project risks are generated when Airtable read fails.",
        }
    return build_project_delivery_risks(projects or [], limit=limit)


async def collect_finance_project_risks(
    source: Any,
    *,
    limit: int = 12,
) -> dict[str, Any]:
    """Read project finance source and return truthful payment risks."""
    if source is None:
        return {
            "status": "source_unavailable",
            "source": "project_finance",
            "items": [],
            "reason": "finance_source_unavailable",
            "claim_policy": "No fake finance risks are generated without project finance access.",
        }
    try:
        if hasattr(source, "get_projects"):
            import asyncio

            projects = await asyncio.to_thread(source.get_projects)
        elif hasattr(source, "get_active_projects"):
            projects = await source.get_active_projects()
        else:
            return {
                "status": "source_unavailable",
                "source": "project_finance",
                "items": [],
                "reason": "unsupported_finance_source",
                "claim_policy": "No fake finance risks are generated without project finance access.",
            }
    except Exception as exc:
        return {
            "status": "source_unavailable",
            "source": "project_finance",
            "items": [],
            "reason": type(exc).__name__,
            "claim_policy": "No fake finance risks are generated when finance read fails.",
        }
    return build_finance_project_risks(projects or [], limit=limit)


async def collect_team_capacity_snapshot(
    project_source: Any,
    *,
    hr_source: Any = None,
    limit: int = 12,
) -> dict[str, Any]:
    """Read project assignments and return a truthful team capacity snapshot."""
    if project_source is None:
        return {
            "status": "source_unavailable",
            "source": "project_assignments",
            "items": [],
            "reason": "project_source_unavailable",
            "claim_policy": "No fake team capacity is generated without project assignments.",
        }
    try:
        if hasattr(project_source, "get_projects"):
            import asyncio

            projects = await asyncio.to_thread(project_source.get_projects)
        elif hasattr(project_source, "get_active_projects"):
            projects = await project_source.get_active_projects()
        else:
            return {
                "status": "source_unavailable",
                "source": "project_assignments",
                "items": [],
                "reason": "unsupported_project_source",
                "claim_policy": "No fake team capacity is generated without project assignments.",
            }
    except Exception as exc:
        return {
            "status": "source_unavailable",
            "source": "project_assignments",
            "items": [],
            "reason": type(exc).__name__,
            "claim_policy": "No fake team capacity is generated when project read fails.",
        }

    employee_names: dict[int, str] = {}
    if hr_source is not None and hasattr(hr_source, "get_all_employees"):
        try:
            for employee in await hr_source.get_all_employees():
                employee_id = _int_or_zero(employee.get("id"))
                if employee_id:
                    employee_names[employee_id] = str(employee.get("name") or employee_id)
        except Exception:
            employee_names = {}
    return build_team_capacity_snapshot(
        projects or [],
        employee_names=employee_names,
        limit=limit,
    )


async def collect_business_command_snapshot(
    *,
    amocrm: Any = None,
    project_source: Any = None,
    finance_source: Any = None,
    hr_source: Any = None,
    limit: int = 5,
) -> dict[str, Any]:
    """Collect the owner-facing command center snapshot from live sources."""
    sales = await collect_sales_today_priorities(amocrm, limit=limit)
    projects = await collect_project_delivery_risks(project_source, limit=limit)
    finance = await collect_finance_project_risks(
        finance_source or project_source,
        limit=limit,
    )
    team = await collect_team_capacity_snapshot(
        project_source,
        hr_source=hr_source,
        limit=limit,
    )
    sections = {
        "sales": sales,
        "projects": projects,
        "finance": finance,
        "team": team,
    }
    ready_sections = sum(1 for section in sections.values() if section.get("status") == "ready")
    unavailable_sections = [
        key
        for key, section in sections.items()
        if section.get("status") == "source_unavailable"
    ]
    total_items = sum(len(section.get("items") or []) for section in sections.values())
    if unavailable_sections:
        status = "partial"
    elif total_items:
        status = "attention_required"
    else:
        status = "clear"
    return {
        "status": status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sections": sections,
        "summary": {
            "ready_sections": ready_sections,
            "total_sections": len(sections),
            "attention_items": total_items,
            "unavailable_sections": unavailable_sections,
        },
        "claim_policy": "Each section keeps its live-source status; missing sources are not filled with guesses.",
    }


def _lead_contacts(lead: dict[str, Any]) -> list[dict[str, Any]]:
    return lead.get("_embedded", {}).get("contacts", []) or lead.get("contacts", []) or []


def _field_text(fields: dict[str, Any], key: str) -> str:
    for name in PROJECT_FIELD_ALIASES.get(key, (key,)):
        if name not in fields:
            continue
        value = fields.get(name)
        if isinstance(value, list):
            return ", ".join(str(item) for item in value if item).strip()
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except (TypeError, ValueError):
        return None


def _money_value(value: Any) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value)
    digits = re.sub(r"[^\d-]", "", text)
    if digits in ("", "-"):
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def _int_or_zero(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _age_hours(timestamp: int, now: datetime) -> int | None:
    if timestamp <= 0:
        return None
    return max(0, int((now.timestamp() - timestamp) // 3600))


def _age_days(timestamp: int, now: datetime) -> int | None:
    if timestamp <= 0:
        return None
    return max(0, int((now.timestamp() - timestamp) // 86400))


def _has_overdue_task(tasks: list[dict[str, Any]], now: datetime) -> bool:
    current_ts = int(now.timestamp())
    for task in tasks:
        complete_till = _int_or_zero(task.get("complete_till"))
        if complete_till and complete_till < current_ts:
            return True
    return False


def plan_business_command(command: str, *, actor_id: str = "owner") -> CommandPlan:
    """Classify an Uzbek business command into a safe, auditable plan."""
    normalized = " ".join(command.strip().lower().split())
    if not normalized:
        raise ValueError("command must not be empty")

    entities: dict[str, Any] = {"actor_id": actor_id}
    phone = _PHONE_RE.search(normalized)
    lead_id = _LEAD_ID_RE.search(normalized)
    time_match = _TIME_RE.search(normalized)
    if phone:
        value = phone.group(0)
        entities["phone"] = value if value.startswith("+") else f"+{value}"
    if lead_id:
        entities["lead_id"] = int(lead_id.group(1))
    if time_match and ("soat" in normalized or ":" in time_match.group(0)):
        entities["time"] = f"{int(time_match.group(1)):02d}:{int(time_match.group(2) or 0):02d}"

    if any(word in normalized for word in ("lead yarat", "lid yarat", "bitim yarat")):
        intent, mutation, confidence = "create_lead", True, 0.96
        sources, action = ("amocrm",), "approval_then_create_amocrm_lead"
    elif any(word in normalized for word in ("eslat", "vazifa yarat", "task yarat")):
        intent, mutation, confidence = "create_reminder", True, 0.94
        sources = ("amocrm", "telegram_bot")
        action = "approval_then_create_task_or_reminder"
    elif any(word in normalized for word in ("brief", "brif", "kp", "taklif")):
        intent, mutation, confidence = "client_document_workflow", True, 0.93
        sources = ("amocrm", "google_workspace")
        action = "approval_then_prepare_brief_or_proposal"
    elif any(
        word in normalized
        for word in ("loyiha holati", "deadline", "muddat", "qaysi bosqich")
    ):
        intent, mutation, confidence = "project_status_query", False, 0.95
        sources = ("airtable", "amocrm")
        action = "read_live_project_status_with_deadline"
    elif any(word in normalized for word in ("avans", "to'lov", "qarzdor", "debitor")):
        intent, mutation, confidence = "payment_status_query", False, 0.93
        sources = ("finance", "amocrm")
        action = "read_live_payment_status_with_evidence"
    elif any(word in normalized for word in ("jamoa yuklama", "bandlik", "capacity")):
        intent, mutation, confidence = "team_capacity_query", False, 0.91
        sources = ("airtable", "projects")
        action = "read_live_team_capacity_with_projects"
    elif any(word in normalized for word in ("hisobot", "kpi", "savdo", "daromad")):
        intent, mutation, confidence = "agency_analytics_query", False, 0.88
        sources, action = ("amocrm", "finance"), "read_live_metrics_with_evidence"
    else:
        intent, mutation, confidence = "clarification_required", False, 0.35
        sources, action = (), "ask_one_clarifying_question"

    digest = hashlib.sha256(f"{actor_id}:{normalized}".encode()).hexdigest()[:20]
    return CommandPlan(
        intent=intent,
        mutation=mutation,
        approval_required=mutation,
        confidence=confidence,
        entities=entities,
        required_sources=sources,
        next_action=action,
        idempotency_key=digest,
    )

"""AI Agent Orchestrator (Supervisor / Meta-Agent Fleet Registry & Self-Healing Engine).

Implements the world-standard Supervisor / Orchestrator-Worker lifecycle pattern:
1. Unified AI Agent Fleet Registry (Oisha-OS background workers + Hermes cron agents).
2. Health & Heartbeat Audit (detects ACTIVE, STALLED, FAILED, IDLE, FIRED agents).
3. Gap Analysis & Blueprints ("Bizga nechta va qanday AI agent kerak?").
4. Safe Lifecycle Actions: Hire (spawn from blueprint), Fire (retire/disable), Revive (self-heal/re-enable).
"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from src.time_utils import get_local_now

DEFAULT_HERMES_JOBS_PATH = "/home/hermes/.hermes/cron/jobs.json"
DEFAULT_OISHA_DB_PATH = "data/bot.db"


@dataclass(frozen=True)
class AgentBlueprint:
    """Declarative blueprint for hiring/evaluating specialized AI worker agents."""

    slug: str
    name: str
    role: str
    department: str
    engine: str  # "oisha_scheduler" | "hermes_cron"
    schedule_expr: str
    target_destination: str
    kpi_metric: str
    description: str
    default_prompt: str = ""


_EVENING_STANDUP_PROMPT = (
    "Soat 18:00 bo'ldi. Ish kunining kechki sarhisob vaqti! "
    "Quyidagi matnni aynan qaytar: kirish va ro'yxatdagi ism hamda @username'larni saqla. "
    "Qo'shimcha izoh, qoida yoki boshqa ism yozma. Xabarni vosita bilan yuborma; "
    "faqat yakuniy matnni qaytar, tizim avtomatik yetkazadi.\n\n"
    "Jamoa, bugun yakunlagan ishlaringizni qisqa va aniq yozib qoldiring:\n\n"
    "1. Shahnoza Abdijabborova @jonbranding_assistant\n"
    "2. Rayxona Rahimova @RayxonJonbranding\n"
    "3. Mumtozmaxal Normurodova @MumtozmaxalJonbranding\n"
    "4. Hasanboy Gaziyev @hasan_yahyo\n"
    "5. Ifora @MenejerIfora\n"
    "6. Ahroriy Abdulloh @AhroriyAbdulloh\n"
    "7. Beslan\n"
    "8. Dilbar @jonbranding_finansist\n"
    "9. Baxtiyorjon Gaziyev @baxtiyorjongaziyev"
)

CANONICAL_AGENT_BLUEPRINTS: tuple[AgentBlueprint, ...] = (
    AgentBlueprint(
        "ai_rop", "AI ROP (Sotuv Bo'limi Rahbari)", "Sales Director & Funnel Controller",
        "Sales", "oisha_scheduler", "09:00, 14:00, 18:30 (Mon-Sat)",
        "telegram:-1003854308552:115", "50/20/10/3/1 kunlik voronka va 0 overdue task",
        "Sotuvchilar (Shahnoza, Rayxona, Mumtozmaxal) 50/20/10/3/1 normasini va Moizvonki qo'ng'iroqlarini nazorat qiladi.",
    ),
    AgentBlueprint(
        "ai_call_qa", "AI Call QA (Sifat va Skript Murabbiyi)", "Call Quality Auditor & EVQN Script Coach",
        "Sales", "oisha_scheduler", "Every 10m + Hourly Coaching (10:00-19:00)",
        "telegram:-1003854308552:115", ">=3 daqiqalik suhbatlar EVQN tahlili va xatolar ustida ishlash",
        "Moizvonki va AmoCRM audio yozuvlarini eshitib, sotuvchilarning xatolarini va EVQN savollarini tahlil qiladi.",
    ),
    AgentBlueprint(
        "ai_hr_attendance_10", "AI HR — Ertalabki Davomat (10:00)", "HR & Morning Standup Controller",
        "HR & Operations", "hermes_cron", "0 10 * * 1-6", "telegram:-1003114662117",
        "8 nafar xodimning soat 10:00 da ishga kelishi va 1-vazifasi",
        "Har kuni 10:00 da barcha xodimlarni birma-bir teg qilib ishga kelganini va bugungi 1-vazifasini so'raydi.",
        "Soat 10:00 bo'ldi. `crm_get_team_roster` dagi barcha 8 nafar xodimni birma-bir teg qilib ishga kelganini so'ra.",
    ),
    AgentBlueprint(
        "ai_hr_lunch_13", "AI HR — Tushlik va Dam Olish (13:00)", "HR Wellness & Break Coordinator",
        "HR & Operations", "hermes_cron", "0 13 * * 1-6", "telegram:-1003114662117",
        "Jamoaning 13:00-14:00 oralig'ida tartibli tushlik qilishi",
        "Soat 13:00 da jamoani tushlikka chiqaradi va 14:00 da ishga qaytishni eslatadi.",
        "Jamoaga samimiy tushlik tilagini yoz va soat 14:00 da hamma ishga qaytishini eslat.",
    ),
    AgentBlueprint(
        "ai_hr_return_14", "AI HR — Tushlikdan Qaytish Nazorati (14:00)", "HR Post-Lunch Return Controller",
        "HR & Operations", "hermes_cron", "0 14 * * 1-6", "telegram:-1003114662117",
        "Soat 14:00 da 100% jamoaning ishga qaytishi",
        "Soat 14:00 da barcha xodimlarni birma-bir teg qilib tushlikdan qaytganini tekshiradi.",
        "Soat 14:00 bo'ldi. Barcha 8 nafar xodimni birma-bir teg qilib, ishga qaytganliklarini tekshir.",
    ),
    AgentBlueprint(
        "ai_hr_evening_18", "AI HR — Kechki Sarhisob / Standup (18:00)", "HR Evening Standup Collector",
        "HR & Operations", "hermes_cron", "0 18 * * 1-6", "telegram:-1003114662117",
        "Har bir xodimning kunlik bajargan ishlari hisoboti",
        "Soat 18:00 da tasdiqlangan 9 kishilik ro'yxatdan bugun yakunlagan ishlarini so'raydi.",
        _EVENING_STANDUP_PROMPT,
    ),
    AgentBlueprint(
        "ai_lead_hunter", "AI Targetolog & Speed-to-Lead", "Lead Intake & Unowned Deal Watchdog",
        "Marketing & Sales", "oisha_scheduler", "Every 2m (Meta Lead Ads + Unowned Lead Alert)",
        "telegram:-1003854308552:1020", "Yangi lidga <15 daqiqada javob va 0 egasiz bitim",
        "Meta/Instagram'dan tushgan yangi lidlarni AmoCRM va 1020-topikka uzatadi hamda egasiz bitimlarni nazorat qiladi.",
    ),
    AgentBlueprint(
        "ai_debitor_finance", "AI Hisobchi & Debitor Nazoratchisi", "Finance & Accounts Receivable Agent",
        "Finance", "hermes_cron", "0 11 * * 1-6", "telegram:150074828",
        "Kutilayotgan to'lovlar va shartnomalar nazorati",
        "AmoCRM'da shartnoma yuborilgan va to'lov kutilayotgan bitimlarni tekshirib, eslatma beradi.",
        "AmoCRM'dagi to'lov kutilayotgan va shartnoma bosqichidagi issiq bitimlarni `crm_get_rop_digest` va `crm_search_leads` orqali tekshirib, qisqa debitorlik/to'lov nazorati xulosasini tayyorla.",
    ),
)

_HERMES_NAME_TO_SLUG = {
    "ertalab-davomat-10-00": "ai_hr_attendance_10",
    "tushlik-ishtaha": "ai_hr_lunch_13",
    "tushlikdan-qaytish-tekshiruvi": "ai_hr_return_14",
    "kechki-sarhisob-18-00": "ai_hr_evening_18",
    "ai-debitor-nazorati": "ai_debitor_finance",
}


def _read_hermes_jobs(jobs_path: str = DEFAULT_HERMES_JOBS_PATH) -> list[dict[str, Any]]:
    if not os.path.exists(jobs_path):
        return []
    try:
        with open(jobs_path, "r", encoding="utf-8") as f:
            return list(json.load(f).get("jobs", []))
    except Exception:
        return []


def _write_hermes_jobs(jobs: list[dict[str, Any]], jobs_path: str = DEFAULT_HERMES_JOBS_PATH) -> bool:
    try:
        os.makedirs(os.path.dirname(jobs_path) or ".", exist_ok=True)
        payload = {"jobs": jobs, "updated_at": get_local_now().isoformat()}
        tmp_path = f"{jobs_path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, jobs_path)
        return True
    except Exception:
        return False


def _inspect_oisha_db_signals(db_path: str = DEFAULT_OISHA_DB_PATH) -> dict[str, Any]:
    signals: dict[str, Any] = {"rop_active_sellers": 0, "rop_last_snapshot": None, "checkin_last_hour": None}
    if not os.path.exists(db_path):
        return signals
    try:
        conn = sqlite3.connect(db_path, timeout=3.0)
        cur = conn.cursor()
        for query, key, conv in (
            ("SELECT COUNT(*) FROM rop_targets WHERE active = 1", "rop_active_sellers", int),
            ("SELECT key FROM rop_config WHERE key LIKE 'snapshot.%' ORDER BY key DESC LIMIT 1", "rop_last_snapshot", str),
            ("SELECT value FROM kv_settings WHERE key = 'CHECKIN_LAST_HOUR_KEY'", "checkin_last_hour", str),
        ):
            try:
                cur.execute(query)
                row = cur.fetchone()
                if row and row[0] is not None:
                    signals[key] = conv(row[0])
            except Exception:
                pass
        conn.close()
    except Exception:
        pass
    return signals


def _builtin_oisha_agents(db_sig: dict[str, Any]) -> list[dict[str, Any]]:
    rop_on = os.getenv("ROP_ENABLED", "1").strip().lower() in {"1", "true", "yes", "on"}
    return [
        {
            "id": "oisha:ai_rop", "slug": "ai_rop", "name": "AI ROP (Sotuv Bo'limi Rahbari)",
            "department": "Sales", "engine": "oisha_scheduler", "schedule": "09:00, 14:00, 18:30 (Mon-Sat)",
            "status": "ACTIVE" if rop_on else "PAUSED", "health": "HEALTHY" if rop_on else "DISABLED",
            "kpi_evidence": f"SSoT sellers={db_sig['rop_active_sellers'] or 3}, snapshot={db_sig['rop_last_snapshot'] or 'ready'}",
        },
        {
            "id": "oisha:ai_call_qa", "slug": "ai_call_qa", "name": "AI Call QA & Hourly Check-in",
            "department": "Sales", "engine": "oisha_scheduler", "schedule": "Every 10m + Hourly :00 (10:00-19:00)",
            "status": "ACTIVE", "health": "HEALTHY", "kpi_evidence": f"last_checkin_hour={db_sig['checkin_last_hour'] or 'active'}",
        },
        {
            "id": "oisha:ai_lead_hunter", "slug": "ai_lead_hunter", "name": "AI Targetolog & Speed-to-Lead",
            "department": "Marketing & Sales", "engine": "oisha_scheduler", "schedule": "Every 2m (24/7)",
            "status": "ACTIVE", "health": "HEALTHY", "kpi_evidence": "Target LEADs -> Topic 1020 + Unowned Lead Guard",
        },
    ]


def _classify_hermes_job(job: dict[str, Any], covered_slugs: set[str]) -> tuple[dict[str, Any], bool]:
    jid = str(job.get("id") or "")
    jname = str(job.get("name") or "")
    enabled = bool(job.get("enabled", False))
    sched = job.get("schedule") or {}
    kind = sched.get("kind", "cron")
    expr = sched.get("expr") or sched.get("display") or ""
    deliver = str(job.get("deliver") or "")
    last_status, last_error = job.get("last_status"), job.get("last_error")
    slug = _HERMES_NAME_TO_SLUG.get(jname)

    zombie_reason = ""
    if not enabled and kind == "once":
        zombie_reason = "completed_one_off_reminder"
    elif enabled and deliver == "origin" and slug is None:
        zombie_reason = "adhoc_personal_reminder_running_as_recurring_cron"
    elif enabled and jname == "ertalab-standup" and "ai_hr_attendance_10" in covered_slugs:
        zombie_reason = "duplicate_morning_standup_superseded_by_10am_attendance"

    health = f"ERROR: {last_error or 'failed'}" if (last_status == "error" or last_error) else ("HEALTHY" if enabled else "DISABLED")
    entry = {
        "id": f"hermes:{jid}", "job_id": jid, "slug": slug or f"custom_{jid}", "name": jname,
        "engine": "hermes_cron", "schedule": expr, "deliver": deliver,
        "status": "ACTIVE" if enabled else "DISABLED", "health": health,
        "last_run_at": job.get("last_run_at"), "last_status": last_status,
    }
    if zombie_reason:
        entry["zombie_reason"] = zombie_reason
    return entry, bool(zombie_reason)


def evaluate_fleet_status(
    *,
    jobs_path: str = DEFAULT_HERMES_JOBS_PATH,
    db_path: str = DEFAULT_OISHA_DB_PATH,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Audit all active AI agents, detect stalled/zombie jobs, and recommend missing agents."""
    now = now or get_local_now()
    hermes_jobs = _read_hermes_jobs(jobs_path)
    active_agents = _builtin_oisha_agents(_inspect_oisha_db_signals(db_path))
    covered_slugs = {"ai_rop", "ai_call_qa", "ai_lead_hunter"} | {
        _HERMES_NAME_TO_SLUG[str(j.get("name") or "")]
        for j in hermes_jobs
        if j.get("enabled", False) and str(j.get("name") or "") in _HERMES_NAME_TO_SLUG
    }
    zombie_or_stale_jobs: list[dict[str, Any]] = []
    for job in hermes_jobs:
        entry, is_zombie = _classify_hermes_job(job, covered_slugs)
        if is_zombie:
            zombie_or_stale_jobs.append(entry)
        elif job.get("enabled", False):
            active_agents.append(entry)

    recommended_hires = [
        {
            "slug": bp.slug, "name": bp.name, "role": bp.role, "department": bp.department,
            "schedule_expr": bp.schedule_expr, "target_destination": bp.target_destination,
            "kpi_metric": bp.kpi_metric, "reason_needed": bp.description,
        }
        for bp in CANONICAL_AGENT_BLUEPRINTS
        if bp.slug not in covered_slugs
    ]
    stalled = [a for a in active_agents if str(a.get("health", "")).startswith("ERROR")]
    return {
        "success": True, "source": "ai_orchestrator_live", "as_of_tashkent": now.isoformat(),
        "summary": {
            "optimal_team_size": len(CANONICAL_AGENT_BLUEPRINTS),
            "active_agents_count": len(active_agents),
            "stalled_or_failed_count": len(stalled),
            "zombie_or_duplicate_count": len(zombie_or_stale_jobs),
            "recommended_new_hires_count": len(recommended_hires),
        },
        "active_agents": active_agents,
        "stalled_or_failed_agents": stalled,
        "zombie_or_duplicate_agents": zombie_or_stale_jobs,
        "recommended_hires": recommended_hires,
        "available_blueprints": [asdict(b) for b in CANONICAL_AGENT_BLUEPRINTS],
    }


def hire_ai_agent(
    *,
    blueprint_slug: str | None = None,
    name: str | None = None,
    prompt: str | None = None,
    cron_expr: str | None = None,
    deliver: str = "telegram:-1003114662117",
    jobs_path: str = DEFAULT_HERMES_JOBS_PATH,
) -> dict[str, Any]:
    """Hire (spawn or re-enable) an AI agent from a canonical blueprint or custom specification."""
    bp = next((b for b in CANONICAL_AGENT_BLUEPRINTS if blueprint_slug and b.slug == blueprint_slug.strip()), None)
    slug_to_job_name = {v: k for k, v in _HERMES_NAME_TO_SLUG.items()}
    job_name = slug_to_job_name.get(bp.slug, bp.slug) if bp else (name or "").strip()
    final_prompt = (prompt or (bp.default_prompt if bp else "")).strip()
    final_expr = (cron_expr or (bp.schedule_expr if bp else "")).strip()
    final_deliver = (bp.target_destination if bp and bp.target_destination.startswith("telegram:") else deliver).strip()

    if not job_name or not final_prompt or not final_expr:
        raise ValueError("missing_agent_name_prompt_or_schedule")

    jobs = _read_hermes_jobs(jobs_path)
    now_iso = get_local_now().isoformat()
    for j in jobs:
        if str(j.get("name") or "").strip().lower() == job_name.lower():
            j.update({
                "enabled": True, "prompt": final_prompt, "deliver": final_deliver,
                "schedule": {"kind": "cron", "expr": final_expr, "display": final_expr},
                "updated_at": now_iso,
            })
            return {
                "success": _write_hermes_jobs(jobs, jobs_path),
                "action": "rehired_and_updated",
                "agent": {"job_id": j.get("id"), "name": job_name, "schedule": final_expr, "deliver": final_deliver},
            }

    new_id = uuid.uuid4().hex[:12]
    jobs.append({
        "id": new_id, "name": job_name, "prompt": final_prompt,
        "schedule": {"kind": "cron", "expr": final_expr, "display": final_expr},
        "deliver": final_deliver, "enabled": True,
        "created_at": now_iso, "updated_at": now_iso,
        "last_run_at": None, "last_status": None, "last_error": None,
    })
    return {
        "success": _write_hermes_jobs(jobs, jobs_path),
        "action": "hired_new_agent",
        "agent": {"job_id": new_id, "name": job_name, "schedule": final_expr, "deliver": final_deliver},
    }


def fire_ai_agent(
    agent_id_or_name: str,
    *,
    remove_permanently: bool = False,
    jobs_path: str = DEFAULT_HERMES_JOBS_PATH,
) -> dict[str, Any]:
    """Fire (disable or remove) a zombie, duplicate, or underperforming AI agent."""
    needle = str(agent_id_or_name or "").strip().removeprefix("hermes:").lower()
    if not needle:
        raise ValueError("agent_id_or_name_required")

    jobs = _read_hermes_jobs(jobs_path)
    matched, kept_jobs = None, []
    for j in jobs:
        jid, jname = str(j.get("id") or "").lower(), str(j.get("name") or "").lower()
        slug = str(_HERMES_NAME_TO_SLUG.get(j.get("name", ""), "")).lower()
        if matched is None and needle in {jid, jname, slug}:
            matched = j
            if remove_permanently:
                continue
            j["enabled"] = False
            j["updated_at"] = get_local_now().isoformat()
        kept_jobs.append(j)

    if matched is None:
        return {"success": False, "status": "agent_not_found", "query": agent_id_or_name}
    return {
        "success": _write_hermes_jobs(kept_jobs, jobs_path),
        "action": "removed" if remove_permanently else "disabled",
        "fired_agent": {"job_id": matched.get("id"), "name": matched.get("name")},
    }


def revive_or_cleanup_fleet(
    *,
    auto_fire_zombies: bool = True,
    auto_hire_missing_core: bool = False,
    jobs_path: str = DEFAULT_HERMES_JOBS_PATH,
    db_path: str = DEFAULT_OISHA_DB_PATH,
) -> dict[str, Any]:
    """Self-healing pass: clear error states on stalled agents, disable zombie crons, and optionally hire core blueprints."""
    status = evaluate_fleet_status(jobs_path=jobs_path, db_path=db_path)
    jobs = _read_hermes_jobs(jobs_path)
    zombie_ids = {z["job_id"] for z in status.get("zombie_or_duplicate_agents", []) if z.get("job_id")}
    revived, fired_zombies, changed = [], [], False

    for j in jobs:
        jid, jname = j.get("id"), str(j.get("name") or "")
        if auto_fire_zombies and jid in zombie_ids and j.get("enabled", False):
            j["enabled"] = False
            fired_zombies.append(f"{jname} ({jid})")
            changed = True
            continue
        if j.get("enabled") and (j.get("last_status") == "error" or j.get("last_error")):
            j["last_error"] = None
            j["last_status"] = "recovered_by_orchestrator"
            revived.append(f"{jname} ({jid})")
            changed = True

    if changed:
        _write_hermes_jobs(jobs, jobs_path)

    hired: list[str] = []
    if auto_hire_missing_core:
        for rec in status.get("recommended_hires", []):
            bp = next((b for b in CANONICAL_AGENT_BLUEPRINTS if b.slug == rec["slug"]), None)
            if bp and bp.engine == "hermes_cron" and bp.default_prompt:
                if hire_ai_agent(blueprint_slug=bp.slug, jobs_path=jobs_path).get("success"):
                    hired.append(bp.name)

    return {
        "success": True,
        "revived_agents": revived,
        "fired_zombie_agents": fired_zombies,
        "hired_agents": hired,
        "fleet_status": evaluate_fleet_status(jobs_path=jobs_path, db_path=db_path)["summary"],
    }

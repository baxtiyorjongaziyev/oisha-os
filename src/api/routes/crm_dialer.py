"""FastAPI Router for Jon CRM Web-App (amoCRM 1:1 UI powered by Twenty CRM Backend Engine)."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel

from src.api.crm_access import ensure_crm_permission, require_dialer_access
from src.services.core.crm.dialer_service import DialerService, SLUG_TO_TWENTY
from src.services.core.crm.uzbek_crm_hub import UzbekCrmHub
from src.services.core.crm.caller_id_service import CallerIdHub

logger = logging.getLogger(__name__)

router = APIRouter(tags=["crm-dialer"], dependencies=[Depends(require_dialer_access)])
dialer_service = DialerService()
crm_hub = UzbekCrmHub(store=dialer_service.store)
caller_id_hub = CallerIdHub(store=dialer_service.store)

class ActionPayload(BaseModel):
    lead_id: int
    action_slug: str
    note: Optional[str] = None
    next_call_at: Optional[str] = None
    pipeline_id: Optional[int] = None

class LeadCreateUpdatePayload(BaseModel):
    id: Optional[int] = None
    name: str
    contact_name: Optional[str] = None
    company_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    price: Optional[float] = 0.0
    status_slug: Optional[str] = "yangi"
    status_id: Optional[int] = None
    responsible_user_id: Optional[int] = None
    responsible_name: Optional[str] = "Shahnoza Abdijabborova"
    pipeline_id: Optional[int] = 11162698
    source: Optional[str] = None
    tags: Optional[List[str]] = None
    custom_fields: Optional[Dict[str, Any]] = None
    files: Optional[List[Dict[str, Any]]] = None
    last_audio_url: Optional[str] = None
    last_audio_duration: Optional[int] = None

class NoteAddPayload(BaseModel):
    text: str
    note_type: str = "note"

class FileAddPayload(BaseModel):
    name: str
    url: str
    file_type: str = "document"

class TaskCreatePayload(BaseModel):
    lead_id: int
    title: str
    task_type: str = "Qo'ng'iroq qilish"
    responsible_name: str = "Shahnoza Abdijabborova"
    due_at: Optional[str] = None

class TaskCompletePayload(BaseModel):
    result_text: str = "Bajarildi"

class ChatMessagePayload(BaseModel):
    lead_id: int
    text: str
    channel: str = "Telegram"

@router.get("/api/crm/dialer/catalog")
async def get_crm_catalog() -> Dict[str, Any]:
    """Retrieve all 9 pipelines, statuses, 21 BANT/SPIN custom fields schema, sellers, and Twenty backend info."""
    return dialer_service.get_catalog()

@router.get("/api/crm/dialer/queue")
async def get_dialer_queue(
    rep_id: Optional[int] = None,
    status: Optional[str] = None,
    q: Optional[str] = None,
    pipeline_id: Optional[int] = None,
    tag: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=500),
) -> Dict[str, Any]:
    """Retrieve filtered list of leads in call queue."""
    leads = dialer_service.get_queue(
        rep_id=rep_id, status=status, search=q, limit=limit, pipeline_id=pipeline_id, tag=tag
    )
    return {"total": len(leads), "leads": leads, "backend_engine": "twenty-crm"}

@router.get("/api/crm/dialer/next")
async def get_next_lead(
    rep_id: Optional[int] = None,
    status: Optional[str] = None,
    exclude_id: Optional[int] = None,
    pipeline_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Fetch next single priority lead for the caller."""
    lead = dialer_service.get_next_lead(
        rep_id=rep_id, status=status, exclude_id=exclude_id, pipeline_id=pipeline_id
    )
    stats = dialer_service.store.get_stats(rep_id=rep_id, pipeline_id=pipeline_id)
    return {"lead": lead, "stats": stats}

@router.post("/api/crm/dialer/action")
async def record_dialer_action(
    payload: ActionPayload,
    actor: Dict[str, Any] = Depends(require_dialer_access),
) -> Dict[str, Any]:
    """Submit call outcome or Kanban Drag-and-Drop stage move and sync to Twenty CRM backend."""
    return await dialer_service.submit_action(
        lead_id=payload.lead_id,
        action_slug=payload.action_slug,
        seller_name=actor["name"],
        note=payload.note,
        next_call_at=payload.next_call_at,
        pipeline_id=payload.pipeline_id,
    )

@router.get("/api/crm/dialer/lead/{lead_id}")
async def get_lead_details(lead_id: int) -> Dict[str, Any]:
    """Retrieve full details of a single lead including BANT/SPIN fields, files, and call history."""
    lead = dialer_service.store.get_lead_detail(lead_id)
    if not lead:
        return {"error": "Lead not found"}
    return {"lead": lead, "backend_engine": "twenty-crm"}

@router.post("/api/crm/dialer/lead")
async def create_or_update_lead(payload: LeadCreateUpdatePayload) -> Dict[str, Any]:
    """Create a new lead or update an existing one and write-through to Twenty CRM backend."""
    lead_data = payload.model_dump(exclude_unset=True) if hasattr(payload, "model_dump") else payload.dict(exclude_unset=True)
    lead_id = await dialer_service.save_lead_with_twenty(lead_data)
    return {"success": True, "lead_id": lead_id, "lead": dialer_service.store.get_lead_detail(lead_id)}

@router.post("/api/crm/dialer/lead/{lead_id}/note")
async def add_lead_note(
    lead_id: int,
    payload: NoteAddPayload,
    actor: Dict[str, Any] = Depends(require_dialer_access),
) -> Dict[str, Any]:
    """Append a note or task to a lead's timeline and sync to Twenty CRM."""
    ok = dialer_service.store.add_lead_note(
        lead_id=lead_id, text=payload.text, author=actor["name"], note_type=payload.note_type
    )
    lead = dialer_service.store.get_lead_detail(lead_id)
    if ok and lead:
        twenty_stage = SLUG_TO_TWENTY.get(lead.get("status_slug") or "yangi", "NEW")
        asyncio.create_task(dialer_service.twenty.upsert_opportunity_full(lead, twenty_stage=twenty_stage))
    return {"success": ok, "lead": lead}

@router.post("/api/crm/dialer/lead/{lead_id}/file")
async def add_lead_file(
    lead_id: int,
    payload: FileAddPayload,
    actor: Dict[str, Any] = Depends(require_dialer_access),
) -> Dict[str, Any]:
    """Attach a file/link (KP, Shartnoma, Brief, Brandbook) to a deal card and sync to Twenty CRM."""
    ok = dialer_service.store.add_lead_file(
        lead_id=lead_id,
        name=payload.name,
        url=payload.url,
        file_type=payload.file_type,
        uploaded_by=actor["name"],
    )
    lead = dialer_service.store.get_lead_detail(lead_id)
    if ok and lead:
        twenty_stage = SLUG_TO_TWENTY.get(lead.get("status_slug") or "yangi", "NEW")
        asyncio.create_task(dialer_service.twenty.upsert_opportunity_full(lead, twenty_stage=twenty_stage))
        from src.services.core.crm.amocrm_dialer_syncer import sync_note_to_amocrm
        asyncio.create_task(sync_note_to_amocrm(lead_id=lead_id, text=f"📎 Hujjat: {payload.name} ({payload.url})", author=actor["name"]))
    return {"success": ok, "lead": lead}

@router.post("/api/crm/dialer/lead/{lead_id}/ai-analyze")
@router.post("/api/crm/dialer/lead/{lead_id}/ai-analysis")
async def analyze_lead_ai(lead_id: int) -> Dict[str, Any]:
    """Generate BANT/SPIN AI coaching and call analysis for a deal and sync to Twenty CRM."""
    analysis = dialer_service.generate_ai_deal_analysis(lead_id)
    lead = dialer_service.store.get_lead_detail(lead_id)
    if "error" not in analysis and lead:
        twenty_stage = SLUG_TO_TWENTY.get(lead.get("status_slug") or "yangi", "NEW")
        asyncio.create_task(dialer_service.twenty.upsert_opportunity_full(lead, twenty_stage=twenty_stage))
    return {"success": "error" not in analysis, "analysis": analysis}

@router.get("/api/crm/dialer/stats")
async def get_dialer_stats(
    rep_id: Optional[int] = None,
    pipeline_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Retrieve today's calling performance and status/pipeline breakdown."""
    return dialer_service.store.get_stats(rep_id=rep_id, pipeline_id=pipeline_id)

@router.get("/api/crm/dialer/kanban")
async def get_kanban_data(
    rep_id: Optional[int] = None,
    pipeline_id: int = 11162698,
    q: Optional[str] = None,
    tag: Optional[str] = None,
) -> Dict[str, Any]:
    """Retrieve Kanban board columns for any of the 9 pipelines."""
    return dialer_service.get_kanban_board(
        rep_id=rep_id, pipeline_id=pipeline_id, search=q, tag=tag
    )

@router.post("/api/crm/dialer/sync")
async def sync_dialer_leads(
    mode: str = Query(default="both_pull", description="both_pull | amocrm_pull | twenty_pull | twenty_push | backup_seed"),
    include_lost: bool = False,
    actor: Dict[str, Any] = Depends(require_dialer_access),
) -> Dict[str, Any]:
    """Sync between amoCRM, Twenty CRM backend (`crm.jonbranding.uz`), and local cache."""
    if mode != "both_pull":
        ensure_crm_permission(actor, "manage_automations")
    if mode == "twenty_push":
        res = await dialer_service.push_all_to_twenty_backend()
        return {"success": True, "mode": mode, **res}
    if mode == "backup_seed":
        count = dialer_service.seed_from_backup_file(include_lost=include_lost)
        return {"success": True, "mode": mode, "ingested_count": count}
    if mode == "amocrm_pull":
        c_amo = await dialer_service.pull_from_amocrm()
        return {"success": True, "mode": mode, "ingested_count": c_amo}
    if mode == "both_pull":
        c_amo = await dialer_service.pull_from_amocrm()
        c_twenty = await dialer_service.pull_from_twenty_backend()
        return {"success": True, "mode": mode, "ingested_count": c_amo + c_twenty, "amocrm": c_amo, "twenty": c_twenty}
    pulled = await dialer_service.pull_from_twenty_backend()
    return {"success": True, "mode": "twenty_pull", "ingested_count": pulled}

@router.get("/api/crm/dialer/dashboard")
async def get_crm_dashboard(pipeline_id: int = 11162698) -> Dict[str, Any]:
    """1-bo'lim: Ish stoli (amoCRM Rabochiy stol) vidjetlari va analitikasi."""
    return crm_hub.get_dashboard_overview(pipeline_id=pipeline_id)

@router.get("/api/crm/dialer/tasks")
async def get_crm_tasks(
    status: str = "open",
    responsible_name: Optional[str] = None,
    limit: int = 100,
) -> Dict[str, Any]:
    """3-bo'lim: Vazifalar (Tasks) ro'yxati va muddatlar kesimi."""
    return crm_hub.get_tasks(status_filter=status, responsible_name=responsible_name, limit=limit)

@router.post("/api/crm/dialer/tasks")
async def create_crm_task(payload: TaskCreatePayload) -> Dict[str, Any]:
    """Yangi vazifa yaratish va Twenty CRM ga timeline/task sifatida yuborish."""
    res = crm_hub.create_task(
        lead_id=payload.lead_id,
        title=payload.title,
        task_type=payload.task_type,
        responsible_name=payload.responsible_name,
        due_at=payload.due_at,
    )
    asyncio.create_task(
        dialer_service.twenty.create_task(
            title=f"[{payload.task_type}] {payload.title}",
            body=f"Mas'ul: {payload.responsible_name} | Bitim #{payload.lead_id}",
        )
    )
    return res

@router.post("/api/crm/dialer/tasks/{task_id}/complete")
async def complete_crm_task(task_id: int, payload: TaskCompletePayload) -> Dict[str, Any]:
    """Vazifani bajarildi deb yopish."""
    return crm_hub.complete_task(task_id=task_id, result_text=payload.result_text)

@router.get("/api/crm/dialer/directory")
async def get_crm_directory(
    entity_type: str = Query(default="contacts", description="contacts | companies"),
    q: Optional[str] = None,
) -> Dict[str, Any]:
    """4-bo'lim: Kontaktlar va Kompaniyalar yagona reestri."""
    return crm_hub.get_contacts_and_companies(entity_type=entity_type, search=q)

@router.get("/api/crm/dialer/inbox")
async def get_crm_inbox(limit: int = 80) -> Dict[str, Any]:
    """5-bo'lim: Yagona Chat (Telegram, Instagram, Meta Ads, IP-telefoniya)."""
    return crm_hub.get_unified_inbox(limit=limit)

@router.post("/api/crm/dialer/inbox/send")
async def send_crm_inbox_message(
    payload: ChatMessagePayload,
    actor: Dict[str, Any] = Depends(require_dialer_access),
) -> Dict[str, Any]:
    """Yagona Chat yoki Bitim kartochkasidan mijozga xabar (Telegram, Instagram, Izoh) yuborish."""
    is_note = payload.channel in ("note", "izoh", "Ichki Izoh")
    channel_tag = "Ichki Izoh" if is_note else payload.channel
    note_type = "note" if is_note else ("telegram_out" if "Telegram" in payload.channel else "instagram_out")

    text = f"💬 [{channel_tag}] {payload.text}" if not is_note else f"📝 [Izoh] {payload.text}"
    ok = dialer_service.store.add_lead_note(
        lead_id=payload.lead_id, text=text, author=actor["name"], note_type=note_type
    )
    lead = dialer_service.store.get_lead_detail(payload.lead_id)
    sent_status = False

    if not is_note:
        try:
            from src.services.core.crm.omnichannel_hub import OmnichannelHub
            hub = OmnichannelHub()
            chan = "Telegram" if "Telegram" in payload.channel else "Instagram Direct"
            res = await hub.send_outbound_reply_async(
                lead_id=payload.lead_id,
                channel=chan,
                text=payload.text,
                sender_name=actor["name"],
            )
            sent_status = res.get("sent", False)
        except Exception as hub_err:
            logger.warning("[INBOX-SEND] Hub error: %s", hub_err)

    if ok and lead:
        twenty_stage = SLUG_TO_TWENTY.get(lead.get("status_slug") or "yangi", "NEW")
        asyncio.create_task(dialer_service.twenty.upsert_opportunity_full(lead, twenty_stage=twenty_stage))

    return {"success": ok, "sent": sent_status, "lead": lead}

@router.get("/api/crm/dialer/bootstrap")
async def get_crm_bootstrap(
    pipeline_id: int = 11162698,
    rep_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Single-request bootstrap: catalog + kanban + queue + dashboard in 1 round-trip for instant (<15ms) startup."""
    return {
        "backend_engine": "twenty-crm",
        "catalog": dialer_service.get_catalog(),
        "kanban": dialer_service.get_kanban_board(rep_id=rep_id, pipeline_id=pipeline_id),
        "queue": dialer_service.get_queue(rep_id=rep_id, pipeline_id=pipeline_id, limit=60, slim=True),
        "dashboard": crm_hub.get_dashboard_overview(pipeline_id=pipeline_id),
    }

@router.get("/api/crm/dialer/events")
async def get_crm_events(limit: int = 80) -> Dict[str, Any]:
    """Analitika -> Hodisalar ro'yxati (Список событий) va qo'ng'iroqlar jurnali."""
    leads = dialer_service.store.get_queue(limit=limit, include_closed=True, slim=False)
    events = []
    for l in leads[:60]:
        events.append({
            "date": (l.get("updated_at") or "Bugun 14:22")[:16],
            "author": l.get("responsible_name") or "Oisha AI",
            "object_type": "Bitim",
            "object_name": l.get("name") or f"Bitim #{l['id']}",
            "lead_id": l["id"],
            "event_name": "Bosqich / Suhbat yangilandi",
            "before_val": "Yangi LEads",
            "after_val": l.get("status_slug") or "qayta_aloqa",
            "audio_url": l.get("last_audio_url") or "",
            "phone": l.get("phone") or "",
        })
    return {"total": len(events), "events": events}

@router.get("/api/crm/dialer/caller-id/active")
async def get_active_caller_id(rep_slug: str = "shahnoza") -> Dict[str, Any]:
    """Sotuvchi ekrani uchun faol kiruvchi qo'ng'iroq pop-up ma'lumotlari."""
    event = caller_id_hub.get_active_ring(rep_slug=rep_slug)
    return {"active": event is not None, "call": event}

@router.post("/api/crm/dialer/caller-id/dismiss")
async def dismiss_caller_id(rep_slug: str = "shahnoza", call_id: Optional[str] = None) -> Dict[str, Any]:
    """Caller ID pop-upini ekrandan yopish."""
    caller_id_hub.dismiss_ring(rep_slug=rep_slug, call_id=call_id)
    return {"success": True}

@router.post("/api/crm/dialer/incoming-call")
async def receive_inbound_ring(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Moizvonki call.start hodisasi yoki to'g'ridan-to'g'ri ring webhook."""
    phone = payload.get("phone") or payload.get("client_number") or payload.get("client_phone") or ""
    account = payload.get("user_account") or payload.get("user_login") or payload.get("manager_name") or ""
    call_id = payload.get("call_id") or ""
    event = caller_id_hub.process_incoming_ring(phone=phone, account=account, call_id=call_id)
    return {"success": True, "event": event}

@router.get("/api/crm/dialer/saas")
async def get_crm_saas_settings() -> Dict[str, Any]:
    """7-bo'lim: O'zbekcha amoCRM Multi-Tenant SaaS va Integratsiyalar sozlamalari."""
    return crm_hub.get_saas_settings()

@router.get("/static/{filename}")
async def serve_crm_static_asset(filename: str) -> Response:
    """Serve sotuv JS/CSS static assets reliably across local and production environments."""
    static_dir = (Path(__file__).resolve().parent.parent.parent / "static").resolve()
    allowed_files = {
        p.name: p
        for p in static_dir.iterdir()
        if p.is_file() and (p.name.startswith("sotuv") or p.name.startswith("amo") or p.name in ("manifest.json", "favicon.ico"))
    }
    file_path = allowed_files.get(filename)
    if file_path is None:
        return Response("Not found", status_code=404)
    media = "text/css" if file_path.suffix == ".css" else "application/javascript" if file_path.suffix == ".js" else "application/json" if file_path.suffix == ".json" else "text/html"
    return Response(content=file_path.read_text(encoding="utf-8"), media_type=media)

@router.get("/sotuv", response_class=HTMLResponse)
@router.get("/sotuv/", response_class=HTMLResponse)
@router.get("/crm", response_class=HTMLResponse)
@router.get("/crm/", response_class=HTMLResponse)
@router.get("/dialer", response_class=HTMLResponse)
@router.get("/dialer/", response_class=HTMLResponse)
async def serve_dialer_app() -> HTMLResponse:
    html_path = Path(__file__).resolve().parent.parent.parent / "static" / "sotuv.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h2>Sotuv Dialer topilmadi.</h2>", status_code=404)

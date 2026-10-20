"""Oddiy CRM — bitta sahifa, katta tugmalar, ma'lumot to'g'ridan-to'g'ri amoCRM'ga.

Sotuvchi uchun faqat uchta harakat: yangi mijoz, qo'ng'iroq natijasi, bosqichni
o'zgartirish. Hammasi amoCRM "Sotuv" voronkasiga yoziladi; Twenty'ga mavjud
bir tomonlama amoCRM → Twenty sinxroni orqali tushadi.
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

from src.api.rbac import Permission, Principal, require_permissions
from src.api.routes.state import api_state
from src.services.core.crm.amocrm_pipeline_config import (
    SALES_CLOSING_STATUS_ID,
    SALES_CONTACT_STATUS_ID,
    SALES_MEETING_STATUS_ID,
    SALES_NEW_STATUS_ID,
    SALES_PIPELINE_ID,
    SALES_QUALIFICATION_STATUS_ID,
    STATUS_WON,
)

router = APIRouter(tags=["simple-crm"])
logger = logging.getLogger(__name__)

STATUS_LOST = 143

# Tartib muhim: "Keyingi bosqich" tugmasi shu ro'yxat bo'yicha yuradi.
STAGES: List[Dict[str, Any]] = [
    {"key": "new", "title": "Yangi", "status_id": SALES_NEW_STATUS_ID},
    {"key": "contact", "title": "Gaplashdik", "status_id": SALES_CONTACT_STATUS_ID},
    {"key": "qualify", "title": "Qiziqdi", "status_id": SALES_QUALIFICATION_STATUS_ID},
    {"key": "meeting", "title": "Uchrashuv", "status_id": SALES_MEETING_STATUS_ID},
    {"key": "closing", "title": "Kelishyapmiz", "status_id": SALES_CLOSING_STATUS_ID},
    {"key": "won", "title": "Sotildi", "status_id": STATUS_WON},
    {"key": "lost", "title": "Rad etdi", "status_id": STATUS_LOST},
]
_STAGE_BY_KEY = {s["key"]: s for s in STAGES}
_BOARD_STAGES = [s for s in STAGES if s["key"] not in {"won", "lost"}]

CALL_RESULTS = {
    "talked": "Gaplashdik",
    "no_answer": "Javob bermadi",
    "call_back": "Keyin qo'ng'iroq qilish kerak",
}

_PHONE_RE = re.compile(r"^\+?[0-9 ()-]{7,20}$")


class NewLead(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    phone: str = Field(min_length=7, max_length=20)
    note: str = Field(default="", max_length=1000)


class CallLog(BaseModel):
    result: str
    note: str = Field(default="", max_length=1000)


class StageChange(BaseModel):
    stage: str


def _amocrm():
    amocrm = api_state.amocrm_instance
    if amocrm is None and api_state.db_instance:
        from src.api.routes.amocrm_integration import _get_amocrm_instance

        amocrm = _get_amocrm_instance()
    if amocrm is None:
        raise HTTPException(status_code=503, detail="amoCRM ulanmagan")
    return amocrm


def _who(principal: Principal) -> str:
    return f"[Oddiy CRM, {principal.role.value} {principal.subject}]"


@router.get("/crm", response_class=HTMLResponse)
async def simple_crm_page(request: Request):
    if not request.cookies.get("oisha_token"):
        return RedirectResponse(url="/api/auth/telegram/login")
    return HTMLResponse(_PAGE)


@router.get("/api/simple-crm/board")
async def board(principal: Principal = require_permissions(Permission.LEAD_WRITE)):
    amocrm = _amocrm()
    columns = []
    for stage in _BOARD_STAGES:
        leads = await amocrm.get_leads(
            status_id=stage["status_id"],
            limit=50,
            **{"filter[statuses][0][pipeline_id]": SALES_PIPELINE_ID},
        )
        columns.append(
            {
                "key": stage["key"],
                "title": stage["title"],
                "leads": [
                    {"id": lead.get("id"), "name": lead.get("name") or "Nomsiz"}
                    for lead in (leads or [])
                    if lead.get("id")
                ],
            }
        )
    return {
        "columns": columns,
        "stages": [{"key": s["key"], "title": s["title"]} for s in STAGES],
        "call_results": CALL_RESULTS,
    }


@router.post("/api/simple-crm/leads")
async def create_lead(
    body: NewLead, principal: Principal = require_permissions(Permission.LEAD_WRITE)
):
    phone = body.phone.strip()
    if not _PHONE_RE.match(phone):
        raise HTTPException(status_code=422, detail="Telefon raqam noto'g'ri")
    amocrm = _amocrm()
    lead_id = await amocrm.create_lead(
        name=body.name.strip(),
        phone=phone,
        pipeline_id=SALES_PIPELINE_ID,
        status_id=SALES_NEW_STATUS_ID,
    )
    if not lead_id:
        raise HTTPException(status_code=502, detail="amoCRM mijozni saqlamadi")
    text = f"{_who(principal)} Yangi mijoz qo'shildi."
    if body.note.strip():
        text += f"\n{body.note.strip()}"
    await asyncio.to_thread(amocrm.add_lead_note, int(lead_id), text)
    return {"ok": True, "lead_id": lead_id}


@router.post("/api/simple-crm/leads/{lead_id}/call")
async def log_call(
    lead_id: int,
    body: CallLog,
    principal: Principal = require_permissions(Permission.LEAD_WRITE),
):
    label = CALL_RESULTS.get(body.result)
    if label is None:
        raise HTTPException(status_code=422, detail="Noma'lum natija")
    text = f"{_who(principal)} Qo'ng'iroq: {label}."
    if body.note.strip():
        text += f"\n{body.note.strip()}"
    result: Optional[Any] = await asyncio.to_thread(
        _amocrm().add_lead_note, lead_id, text
    )
    if not result:
        raise HTTPException(status_code=502, detail="amoCRM izohni saqlamadi")
    return {"ok": True}


@router.post("/api/simple-crm/leads/{lead_id}/stage")
async def change_stage(
    lead_id: int,
    body: StageChange,
    principal: Principal = require_permissions(Permission.LEAD_WRITE),
):
    stage = _STAGE_BY_KEY.get(body.stage)
    if stage is None:
        raise HTTPException(status_code=422, detail="Noma'lum bosqich")
    amocrm = _amocrm()
    ok = await amocrm.update_lead_status(
        lead_id, stage["status_id"], pipeline_id=SALES_PIPELINE_ID
    )
    if not ok:
        raise HTTPException(status_code=502, detail="amoCRM bosqichni o'zgartirmadi")
    await asyncio.to_thread(
        amocrm.add_lead_note,
        lead_id,
        f"{_who(principal)} Bosqich: {stage['title']}.",
    )
    return {"ok": True}


_PAGE = """<!doctype html>
<html lang="uz"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mijozlar</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--ink:#111;--muted:#666;--line:#e3e5e8;--blue:#2563eb;--green:#16a34a;--red:#dc2626}
@media (prefers-color-scheme:dark){:root{--bg:#111315;--card:#1c1f22;--ink:#f2f2f2;--muted:#a0a4a8;--line:#2d3135}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:18px/1.4 system-ui,sans-serif}
header{position:sticky;top:0;background:var(--bg);padding:16px;border-bottom:1px solid var(--line);display:flex;gap:12px;align-items:center}
h1{font-size:24px;margin:0;flex:1}
.big{border:0;border-radius:14px;padding:16px 20px;font-size:20px;font-weight:700;cursor:pointer;color:#fff;background:var(--blue);min-height:60px}
.green{background:var(--green)}.red{background:var(--red)}.ghost{background:var(--line);color:var(--ink)}
main{padding:16px;display:grid;gap:16px;grid-template-columns:repeat(auto-fill,minmax(260px,1fr))}
section{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:12px}
section h2{font-size:20px;margin:4px 4px 12px}section h2 span{color:var(--muted);font-weight:400}
.lead{display:block;width:100%;text-align:left;font-size:19px;padding:16px;margin-bottom:8px;border:1px solid var(--line);border-radius:12px;background:var(--bg);color:var(--ink);cursor:pointer}
.empty{color:var(--muted);padding:8px}
dialog{border:0;border-radius:20px;padding:20px;width:min(480px,94vw);background:var(--card);color:var(--ink)}
dialog h3{margin:0 0 16px;font-size:22px}.col{display:grid;gap:10px}
input,textarea{width:100%;font-size:20px;padding:14px;border:2px solid var(--line);border-radius:12px;background:var(--bg);color:var(--ink)}
label{font-weight:600;display:block;margin:8px 0 4px}
#toast{position:fixed;left:50%;bottom:24px;transform:translateX(-50%);background:#111;color:#fff;padding:14px 22px;border-radius:12px;font-size:18px;display:none}
</style></head><body>
<header><h1>Mijozlar</h1><button class="big green" id="addBtn">+ Yangi mijoz</button></header>
<main id="board"><p class="empty">Yuklanmoqda…</p></main>

<dialog id="addDlg"><h3>Yangi mijoz</h3><form method="dialog" id="addForm" class="col">
<label for="n">Ismi</label><input id="n" required autocomplete="off">
<label for="p">Telefon</label><input id="p" type="tel" required placeholder="+998 90 123 45 67">
<label for="t">Izoh (shart emas)</label><textarea id="t" rows="2"></textarea>
<button class="big green" value="ok">Saqlash</button><button class="big ghost" value="cancel" formnovalidate>Bekor</button>
</form></dialog>

<dialog id="leadDlg"><h3 id="leadName"></h3><div class="col">
<p style="margin:0;color:var(--muted)">Qo'ng'iroq qildingizmi?</p>
<div class="col" id="calls"></div>
<p style="margin:8px 0 0;color:var(--muted)">Mijoz qaysi bosqichda?</p>
<div class="col" id="stages"></div>
<button class="big ghost" id="closeLead">Yopish</button></div></dialog>
<div id="toast"></div>
<script>
let meta={stages:[],call_results:{}},current=null;
const $=id=>document.getElementById(id);
function toast(m){const t=$('toast');t.textContent=m;t.style.display='block';setTimeout(()=>t.style.display='none',2500)}
async function api(path,body){const r=await fetch(path,{method:body?'POST':'GET',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});
 if(r.status===401){location.href='/api/auth/telegram/login';throw 0}
 const d=await r.json().catch(()=>({}));if(!r.ok){toast(d.detail||'Xatolik, qayta urinib ko\\'ring');throw 0}return d}
function btn(text,cls,fn){const b=document.createElement('button');b.className='big '+cls;b.textContent=text;b.onclick=fn;return b}
async function load(){const d=await api('/api/simple-crm/board');meta=d;const board=$('board');board.replaceChildren();
 d.columns.forEach(c=>{const s=document.createElement('section');const h=document.createElement('h2');h.textContent=c.title+' ';
  const n=document.createElement('span');n.textContent=c.leads.length;h.append(n);s.append(h);
  if(!c.leads.length){const e=document.createElement('p');e.className='empty';e.textContent='Hech kim yo\\'q';s.append(e)}
  c.leads.forEach(l=>{const b=document.createElement('button');b.className='lead';b.textContent=l.name;b.onclick=()=>openLead(l,c.key);s.append(b)});
  board.append(s)})}
function openLead(l,stageKey){current=l;$('leadName').textContent=l.name;
 const calls=$('calls');calls.replaceChildren();
 Object.entries(meta.call_results).forEach(([k,v])=>calls.append(btn('📞 '+v,k==='talked'?'green':'ghost',async()=>{await api('/api/simple-crm/leads/'+l.id+'/call',{result:k});toast('Saqlandi ✓');$('leadDlg').close()})));
 const st=$('stages');st.replaceChildren();
 meta.stages.filter(s=>s.key!==stageKey).forEach(s=>st.append(btn(s.title,s.key==='won'?'green':s.key==='lost'?'red':'',async()=>{
  if(s.key==='lost'&&!confirm('Rostdan rad etdimi?'))return;
  await api('/api/simple-crm/leads/'+l.id+'/stage',{stage:s.key});toast('Saqlandi ✓');$('leadDlg').close();load()})));
 $('leadDlg').showModal()}
$('closeLead').onclick=()=>$('leadDlg').close();
$('addBtn').onclick=()=>{$('addForm').reset();$('addDlg').showModal()};
$('addDlg').addEventListener('close',async()=>{if($('addDlg').returnValue!=='ok')return;
 await api('/api/simple-crm/leads',{name:$('n').value,phone:$('p').value,note:$('t').value});toast('Mijoz qo\\'shildi ✓');load()});
load().catch(()=>{});
</script></body></html>"""

"""AI Chat Manager paneli (`/api/chat/`) — Dialoglar, agent sozlamalari, zayavkalar.

Reveo o'rniga o'zimizning yechim (docs/reveo-clone-spec.md, 1-bosqich).
Sahifa `/api/` ostida, chunki production proxy faqat `/api/*` ni FastAPI'ga
yuboradi. Operator yuborgan xabar haqiqatan mijozga ketadi — shuning uchun
`TELEGRAM_SEND` ruxsati kerak; AI hech qachon o'zi yubormaydi.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

from src.api.rbac import Permission, Principal, require_permissions
from src.api.routes.state import api_state
from src.services.core.chat_manager import store
from src.services.core.chat_manager.prompt import build_instructions

router = APIRouter(tags=["chat-manager"])
logger = logging.getLogger(__name__)

_READ = Permission.LEAD_READ_ALL


class ModeChange(BaseModel):
    mode: str


class StarChange(BaseModel):
    starred: bool


class OutgoingMessage(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


def _dialog_or_404(dialog_id: int) -> Dict[str, Any]:
    dialog = store.get_dialog(dialog_id)
    if dialog is None:
        raise HTTPException(status_code=404, detail="Dialog topilmadi")
    return dialog


@router.get("/api/chat/", response_class=HTMLResponse)
async def chat_page(request: Request):
    if not request.cookies.get("oisha_token"):
        return RedirectResponse(url="/api/auth/telegram/login")
    return HTMLResponse(_PAGE)


@router.get("/api/chat/dialogs")
async def dialogs(
    filter: str = "all",
    q: str = "",
    principal: Principal = require_permissions(_READ),
):
    try:
        items = await asyncio.to_thread(store.list_dialogs, filter_key=filter, query=q)
    except ValueError:
        raise HTTPException(status_code=422, detail="Noma'lum filtr")
    counts = await asyncio.to_thread(store.dialog_counts)
    return {"dialogs": items, "counts": counts}


@router.get("/api/chat/dialogs/{dialog_id}")
async def dialog_detail(dialog_id: int, principal: Principal = require_permissions(_READ)):
    dialog = await asyncio.to_thread(_dialog_or_404, dialog_id)
    messages = await asyncio.to_thread(store.get_messages, dialog_id)
    requests_ = await asyncio.to_thread(store.list_requests, dialog_id)
    await asyncio.to_thread(store.mark_read, dialog_id)
    return {"dialog": dialog, "messages": messages, "requests": requests_}


@router.post("/api/chat/dialogs/{dialog_id}/mode")
async def change_mode(
    dialog_id: int,
    body: ModeChange,
    principal: Principal = require_permissions(Permission.LEAD_WRITE),
):
    if body.mode not in store.MODES:
        raise HTTPException(status_code=422, detail="Noma'lum rejim")
    if not await asyncio.to_thread(store.set_mode, dialog_id, body.mode):
        raise HTTPException(status_code=404, detail="Dialog topilmadi")
    return {"ok": True, "mode": body.mode}


@router.post("/api/chat/dialogs/{dialog_id}/star")
async def change_star(
    dialog_id: int,
    body: StarChange,
    principal: Principal = require_permissions(Permission.LEAD_WRITE),
):
    if not await asyncio.to_thread(store.set_starred, dialog_id, body.starred):
        raise HTTPException(status_code=404, detail="Dialog topilmadi")
    return {"ok": True}


async def _send_telegram(external_id: str, text: str) -> None:
    client = api_state.user_client
    if client is None:
        raise HTTPException(status_code=503, detail="Telegram ulanmagan")
    await client.send_message(int(external_id), text)


async def _send_instagram(external_id: str, text: str) -> None:
    from src.services.core.instagram_agent import send_ig_reply
    from src.settings import settings

    token = os.environ.get("META_PAGE_ACCESS_TOKEN", "").strip() or (
        settings.META_PAGE_ACCESS_TOKEN.get_secret_value()
        if settings.META_PAGE_ACCESS_TOKEN else ""
    )
    if not token:
        raise HTTPException(status_code=503, detail="Instagram ulanmagan")
    if not await asyncio.to_thread(send_ig_reply, external_id, text, token):
        raise HTTPException(status_code=502, detail="Instagram xabarni qabul qilmadi")


@router.post("/api/chat/dialogs/{dialog_id}/send")
async def send_message(
    dialog_id: int,
    body: OutgoingMessage,
    principal: Principal = require_permissions(Permission.TELEGRAM_SEND),
):
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Xabar bo'sh")
    dialog = await asyncio.to_thread(_dialog_or_404, dialog_id)
    sender = _send_telegram if dialog["channel"] == "telegram" else _send_instagram
    try:
        await sender(dialog["external_id"], text)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 - surface channel failure, never fake success
        logger.warning("[chat-manager] send failed dialog=%s: %s", dialog_id, exc)
        raise HTTPException(status_code=502, detail="Xabar yuborilmadi")
    # Userbot handleri faqat kiruvchi xabarni ko'radi, shuning uchun panel
    # yuborganini shu yerda yozamiz. Operator yozdi — dialog operatorga o'tadi.
    await asyncio.to_thread(
        store.record_message, dialog["channel"], dialog["external_id"], text,
        direction="out", author="operator",
    )
    await asyncio.to_thread(store.set_mode, dialog_id, "operator")
    return {"ok": True}


@router.get("/api/chat/analitika", response_class=HTMLResponse)
async def analytics_page(request: Request):
    if not request.cookies.get("oisha_token"):
        return RedirectResponse(url="/api/auth/telegram/login")
    from src.api.routes.chat_manager_analytics_page import PAGE

    return HTMLResponse(PAGE)


@router.get("/api/chat/analytics")
async def analytics_data(
    days: int = 7,
    channel: str = "",
    principal: Principal = require_permissions(_READ),
):
    from src.services.core.chat_manager import analytics

    try:
        return await asyncio.to_thread(analytics.build, days, channel)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


class RequestStatusChange(BaseModel):
    status: str


_HAS_PHONE = {"": None, "yes": True, "no": False}


@router.get("/api/chat/zayavkalar", response_class=HTMLResponse)
async def requests_page(request: Request):
    if not request.cookies.get("oisha_token"):
        return RedirectResponse(url="/api/auth/telegram/login")
    from src.api.routes.chat_manager_requests_page import PAGE

    return HTMLResponse(PAGE)


@router.get("/api/chat/requests")
async def requests_list(
    category: str = "",
    status: str = "",
    contact: str = "",
    q: str = "",
    principal: Principal = require_permissions(_READ),
):
    if contact not in _HAS_PHONE:
        raise HTTPException(status_code=422, detail="Noma'lum kontakt filtri")
    try:
        items = await asyncio.to_thread(
            store.list_requests,
            category=category, status=status, has_phone=_HAS_PHONE[contact], query=q,
        )
    except ValueError:
        raise HTTPException(status_code=422, detail="Noma'lum filtr")
    counts = await asyncio.to_thread(store.request_counts)
    return {
        "requests": items,
        "counts": counts,
        "categories": store.REQUEST_CATEGORIES,
        "statuses": {"open": "Ochiq", "taken": "Ishda", "done": "Yopildi"},
    }


@router.post("/api/chat/requests/{request_id}/status")
async def change_request_status(
    request_id: int,
    body: RequestStatusChange,
    principal: Principal = require_permissions(Permission.LEAD_WRITE),
):
    if body.status not in store.REQUEST_STATUSES:
        raise HTTPException(status_code=422, detail="Noma'lum holat")
    if not await asyncio.to_thread(store.set_request_status, request_id, body.status):
        raise HTTPException(status_code=404, detail="Zayavka topilmadi")
    return {"ok": True, "status": body.status}


@router.get("/api/chat/settings")
async def get_agent_settings(principal: Principal = require_permissions(_READ)):
    data = await asyncio.to_thread(store.get_settings)
    return {"settings": data, "instructions": build_instructions(data)}


@router.put("/api/chat/settings")
async def put_agent_settings(
    body: Dict[str, Any],
    principal: Principal = require_permissions(Permission.USERS_MANAGE_LIMITED),
):
    try:
        data = await asyncio.to_thread(store.update_settings, body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"settings": data, "instructions": build_instructions(data)}


@router.post("/api/chat/extract")
async def extract_now(
    principal: Principal = require_permissions(Permission.USERS_MANAGE_LIMITED),
):
    """Zayavka ajratishni darhol ishga tushiradi (jim turish shartisiz)."""
    from src.services.core.chat_manager import extractor
    from src.services.utils.free_ai_router import get_free_ai_router

    amocrm: Optional[Any] = api_state.amocrm_instance
    created = await extractor.run_cycle(get_free_ai_router(), amocrm, min_idle_sec=0)
    return {"ok": True, "created": created}


_PAGE = """<!doctype html>
<html lang="uz"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Dialoglar</title>
<style>
:root{--bg:#f4f6f5;--card:#fff;--ink:#14181a;--muted:#6b7378;--line:#e3e7e5;--brand:#2f9e6b;--brand-soft:#e6f4ec;--out:#2f9e6b;--draft:#fff7e0;--red:#dc2626}
@media (prefers-color-scheme:dark){:root{--bg:#101314;--card:#1a1e20;--ink:#eef1f0;--muted:#9aa3a7;--line:#2a3033;--brand-soft:#173326;--draft:#3a3218}}
*{box-sizing:border-box}html,body{height:100%}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,sans-serif}
.app{display:grid;grid-template-columns:minmax(280px,380px) 1fr;height:100vh}
aside{background:var(--card);border-right:1px solid var(--line);display:flex;flex-direction:column;min-height:0}
aside header{padding:16px 16px 8px}h1{font-size:22px;margin:0 0 2px}.sub{color:var(--muted);font-size:13px;margin:0}
.search{margin:12px 16px 8px;width:calc(100% - 32px);padding:10px 12px;border:1px solid var(--line);border-radius:10px;background:var(--bg);color:var(--ink);font-size:15px}
.tabs{display:flex;gap:6px;padding:0 16px 10px;overflow-x:auto}
.tab{border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:999px;padding:6px 12px;font-size:14px;cursor:pointer;white-space:nowrap}
.tab b{margin-left:6px;color:var(--muted);font-weight:600}.tab.on{background:var(--brand-soft);border-color:var(--brand);color:var(--brand)}
#list{overflow-y:auto;flex:1;padding:0 8px 8px}
.row{display:grid;grid-template-columns:44px 1fr auto;gap:10px;align-items:center;padding:10px;border-radius:12px;cursor:pointer}
.row:hover{background:var(--bg)}.row.on{background:var(--brand-soft)}
.av{width:44px;height:44px;border-radius:50%;display:grid;place-items:center;color:#fff;font-weight:700;position:relative}
.ch{position:absolute;right:-2px;bottom:-2px;width:18px;height:18px;border-radius:50%;border:2px solid var(--card);font-size:9px;display:grid;place-items:center}
.ch.telegram{background:#2aabee}.ch.instagram{background:#d6249f}
.nm{font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.lt{color:var(--muted);font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.meta{text-align:right;font-size:12px;color:var(--muted)}.badge{display:inline-block;margin-top:4px;background:var(--brand);color:#fff;border-radius:999px;padding:1px 7px;font-size:12px;font-weight:700}
.star{color:#8b5cf6}
main{display:flex;flex-direction:column;min-height:0}
.top{display:flex;align-items:center;gap:12px;padding:12px 20px;border-bottom:1px solid var(--line);background:var(--card)}
.top .nm{font-size:17px}.top .sp{flex:1}
.ib{border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:10px;padding:8px 10px;cursor:pointer;font-size:14px}
#reqs{display:flex;gap:8px;flex-wrap:wrap;padding:10px 20px 0}
.req{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--brand);border-radius:10px;padding:8px 12px;font-size:13px;max-width:520px}
.req.complaint{border-left-color:var(--red)}.req b{display:block;font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
#msgs{flex:1;overflow-y:auto;padding:16px 20px;display:flex;flex-direction:column;gap:6px}
.day{align-self:center;background:var(--card);border:1px solid var(--line);border-radius:999px;padding:3px 12px;font-size:12px;color:var(--muted);margin:8px 0}
.m{max-width:min(560px,78%);padding:9px 12px;border-radius:14px;white-space:pre-wrap;word-wrap:break-word}
.m.in{align-self:flex-start;background:var(--card);border:1px solid var(--line)}
.m.out{align-self:flex-end;background:var(--out);color:#fff}
.m.ai_draft{align-self:flex-end;background:var(--draft);color:var(--ink);border:1px dashed #d4a72c}
.m small{display:block;font-size:11px;opacity:.75;margin-top:3px;text-align:right}
.bottom{border-top:1px solid var(--line);background:var(--card);padding:10px 20px 14px}
.modes{display:inline-flex;background:var(--bg);border-radius:10px;padding:3px;margin-bottom:8px}
.mode{border:0;background:transparent;color:var(--muted);padding:6px 14px;border-radius:8px;cursor:pointer;font-weight:600;font-size:14px}
.mode.on{background:var(--card);color:var(--brand);box-shadow:0 1px 2px rgba(0,0,0,.08)}
form{display:flex;gap:8px}textarea{flex:1;resize:none;border:1px solid var(--line);border-radius:12px;padding:10px 12px;font:inherit;background:var(--bg);color:var(--ink)}
.send{border:0;background:var(--brand);color:#fff;border-radius:12px;padding:0 18px;font-weight:700;cursor:pointer}.send:disabled{opacity:.5}
.empty{color:var(--muted);text-align:center;margin:auto;padding:24px}
.back{display:none}
#toast{position:fixed;left:50%;bottom:24px;transform:translateX(-50%);background:#111;color:#fff;padding:12px 20px;border-radius:12px;display:none;z-index:9}
@media (max-width:760px){.app{grid-template-columns:1fr}.app.open aside{display:none}.app:not(.open) main{display:none}.back{display:inline-block}}
</style></head><body>
<div class="app" id="app">
<aside>
 <header><h1>Dialoglar</h1><p class="sub">Telegram va Instagram — bitta joyda · <a href="/api/chat/zayavkalar" style="color:var(--brand)">Zayavkalar →</a></p></header>
 <input class="search" id="q" placeholder="Ism, telefon yoki matn bo'yicha qidirish" autocomplete="off">
 <div class="tabs" id="tabs"></div>
 <div id="list"><p class="empty">Yuklanmoqda…</p></div>
</aside>
<main id="main"><p class="empty">Chap tomondan dialogni tanlang</p></main>
</div>
<div id="toast"></div>
<script>
const $=id=>document.getElementById(id);
const FILTERS=[['all','Barchasi'],['waiting','Javob kutmoqda'],['unread',"O'qilmagan"],['operator','Operator']];
const AUTHOR={client:'Mijoz',ai_draft:'AI qoralama',operator:'Operator'};
const COLORS=['#6366f1','#0ea5e9','#10b981','#f59e0b','#ec4899','#8b5cf6','#14b8a6'];
let filter='all',current=null,timer=null;
function toast(m){const t=$('toast');t.textContent=m;t.style.display='block';setTimeout(()=>t.style.display='none',2500)}
async function api(path,opt={}){const r=await fetch(path,{credentials:'same-origin',headers:{'Content-Type':'application/json'},...opt});
 if(r.status===401){location.href='/api/auth/telegram/login';throw 0}
 const d=await r.json().catch(()=>({}));if(!r.ok){toast(typeof d.detail==='string'?d.detail:'Xatolik');throw 0}return d}
function el(tag,cls,text){const e=document.createElement(tag);if(cls)e.className=cls;if(text!=null)e.textContent=text;return e}
function initials(n){const p=(n||'?').trim().split(/\\s+/);return((p[0]||'?')[0]+(p[1]?p[1][0]:'')).toUpperCase()}
function color(id){return COLORS[id%COLORS.length]}
function ago(ts){const s=Date.now()/1000-ts;if(s<60)return 'hozir';if(s<3600)return Math.floor(s/60)+' daq';if(s<86400)return Math.floor(s/3600)+' soat';return Math.floor(s/86400)+' kun'}
function title(d){return d.name||(d.channel==='telegram'?'Telegram ':'Instagram ')+d.external_id}
function avatar(d){const a=el('div','av',initials(title(d)));a.style.background=color(d.id);const c=el('span','ch '+d.channel,d.channel==='telegram'?'✈':'◎');a.append(c);return a}
async function loadList(){const d=await api('/api/chat/dialogs?filter='+filter+'&q='+encodeURIComponent($('q').value));
 const tabs=$('tabs');tabs.replaceChildren();FILTERS.forEach(([k,label])=>{const b=el('button','tab'+(k===filter?' on':''),label);b.append(el('b',null,d.counts[k]??0));b.onclick=()=>{filter=k;loadList()};tabs.append(b)});
 const list=$('list');list.replaceChildren();if(!d.dialogs.length){list.append(el('p','empty','Dialog yo\\'q'));return}
 d.dialogs.forEach(x=>{const r=el('div','row'+(current===x.id?' on':''));r.append(avatar(x));
  const mid=el('div');const nm=el('div','nm',title(x));if(x.starred)nm.append(el('span','star',' ★'));mid.append(nm,el('div','lt',(x.last_direction==='out'?'Siz: ':'')+x.last_text));
  const meta=el('div','meta',ago(x.last_at));if(x.unread){meta.append(el('br'));meta.append(el('span','badge',x.unread))}
  r.append(mid,meta);r.onclick=()=>openDialog(x.id);list.append(r)})}
function dayLabel(ts){const d=new Date(ts*1000),t=new Date();const y=new Date(t);y.setDate(t.getDate()-1);
 if(d.toDateString()===t.toDateString())return 'Bugun';if(d.toDateString()===y.toDateString())return 'Kecha';return d.toLocaleDateString('uz-UZ',{day:'numeric',month:'long'})}
async function openDialog(id){current=id;$('app').classList.add('open');const d=await api('/api/chat/dialogs/'+id);render(d);loadList().catch(()=>{})}
function render(d){const x=d.dialog,main=$('main');main.replaceChildren();
 const top=el('div','top');const back=el('button','ib back','←');back.onclick=()=>{$('app').classList.remove('open');current=null};
 const info=el('div');info.append(el('div','nm',title(x)),el('div','lt',(x.channel==='telegram'?'Telegram':'Instagram')+(x.phone?' · '+x.phone:'')));
 const star=el('button','ib',x.starred?'★ Belgilangan':'☆ Belgilash');star.onclick=()=>api('/api/chat/dialogs/'+x.id+'/star',{method:'POST',body:JSON.stringify({starred:!x.starred})}).then(()=>openDialog(x.id)).catch(()=>{});
 top.append(back,avatar(x),info,el('div','sp'),star);main.append(top);
 if(d.requests.length){const rq=el('div');rq.id='reqs';const CAT={lead:'Zayavka',interested:'Qiziqqan',complaint:'Shikoyat',suggestion:'Taklif'};
  d.requests.forEach(r=>{const c=el('div','req '+r.category);c.append(el('b',null,CAT[r.category]+(r.amocrm_lead_id?' · amoCRM #'+r.amocrm_lead_id:'')),document.createTextNode(r.summary));rq.append(c)});main.append(rq)}
 const msgs=el('div');msgs.id='msgs';let lastDay='';
 d.messages.forEach(m=>{const dl=dayLabel(m.created_at);if(dl!==lastDay){msgs.append(el('div','day',dl));lastDay=dl}
  const cls=m.author==='ai_draft'?'ai_draft':m.direction;const b=el('div','m '+cls,m.text);
  b.append(el('small',null,AUTHOR[m.author]+' · '+new Date(m.created_at*1000).toLocaleTimeString('uz-UZ',{hour:'2-digit',minute:'2-digit'})));msgs.append(b)});
 if(!d.messages.length)msgs.append(el('p','empty','Xabar yo\\'q'));main.append(msgs);
 const bottom=el('div','bottom');const modes=el('div','modes');
 [['ai','AI-agent'],['operator','Operator']].forEach(([k,label])=>{const b=el('button','mode'+(x.mode===k?' on':''),label);
  b.onclick=()=>api('/api/chat/dialogs/'+x.id+'/mode',{method:'POST',body:JSON.stringify({mode:k})}).then(()=>{toast(k==='ai'?'AI-agent rejimi':'Siz suhbatni oldingiz');openDialog(x.id)}).catch(()=>{});modes.append(b)});
 const f=el('form');const ta=el('textarea');ta.rows=2;ta.placeholder='Xabar yozing… (Enter — yuborish)';const sb=el('button','send','Yuborish');sb.type='submit';
 ta.onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();f.requestSubmit()}};
 f.onsubmit=async e=>{e.preventDefault();const text=ta.value.trim();if(!text)return;if(!confirm('Xabar mijozga yuboriladi. Davom etasizmi?'))return;
  sb.disabled=true;try{await api('/api/chat/dialogs/'+x.id+'/send',{method:'POST',body:JSON.stringify({text})});ta.value='';toast('Yuborildi ✓');setTimeout(()=>openDialog(x.id),800)}catch(_){}finally{sb.disabled=false}};
 f.append(ta,sb);bottom.append(modes,f);main.append(bottom);msgs.scrollTop=msgs.scrollHeight}
let qt;$('q').oninput=()=>{clearTimeout(qt);qt=setTimeout(()=>loadList().catch(()=>{}),300)};
loadList().catch(()=>{});
const startId=Number(new URLSearchParams(location.search).get('d'));if(startId)openDialog(startId).catch(()=>{});
timer=setInterval(()=>{loadList().catch(()=>{});if(current&&!document.querySelector('textarea:focus'))api('/api/chat/dialogs/'+current).then(render).catch(()=>{})},15000);
</script></body></html>"""

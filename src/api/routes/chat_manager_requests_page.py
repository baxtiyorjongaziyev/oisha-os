"""Zayavkalar sahifasi HTML'i (`/api/chat/zayavkalar`) — docs/reveo-clone-spec.md 3.2.

Kategoriya kartalari, kunlar bo'yicha ro'yxat, holat va "Ishga olish".
Ma'lumot `/api/chat/requests` dan; dialog `/api/chat/?d=<id>` da ochiladi.
"""

PAGE = """<!doctype html>
<html lang="uz"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Zayavkalar</title>
<style>
:root{--bg:#f4f6f5;--card:#fff;--ink:#14181a;--muted:#6b7378;--line:#e3e7e5;--brand:#2f9e6b;--brand-soft:#e6f4ec;--red:#dc2626;--amber:#b7791f;--violet:#6d5bd0}
@media (prefers-color-scheme:dark){:root{--bg:#101314;--card:#1a1e20;--ink:#eef1f0;--muted:#9aa3a7;--line:#2a3033;--brand-soft:#173326}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:20px 16px 40px}
h1{font-size:24px;margin:0}.sub{color:var(--muted);margin:2px 0 18px}.sub a{color:var(--brand)}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-bottom:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:16px;cursor:pointer;text-align:left;color:inherit;font:inherit}
.card.on{border:2px solid var(--brand);padding:15px}
.card .top{display:flex;justify-content:space-between;align-items:center}
.ico{width:36px;height:36px;border-radius:10px;display:grid;place-items:center;font-size:18px}
.pill{background:#fdf1dc;color:var(--amber);border-radius:999px;padding:2px 9px;font-size:12px;font-weight:700}
.num{font-size:34px;font-weight:800;margin:10px 0 0;line-height:1}.lbl{color:var(--muted);margin-top:4px}
.bar{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px}
.bar input{flex:1;min-width:220px;padding:11px 14px;border:1px solid var(--line);border-radius:12px;background:var(--card);color:var(--ink);font-size:15px}
.bar select{padding:11px 12px;border:1px solid var(--line);border-radius:12px;background:var(--card);color:var(--ink);font-size:15px}
.list{background:var(--card);border:1px solid var(--line);border-radius:16px;overflow:hidden}
.day{text-align:center;padding:10px 0 4px}.day span{border:1px solid var(--line);border-radius:999px;padding:3px 12px;font-size:12px;color:var(--muted)}
.item{display:grid;grid-template-columns:44px 1fr auto;gap:14px;padding:14px 18px;border-top:1px solid var(--line)}
.day+.item{border-top:0}
.av{width:44px;height:44px;border-radius:50%;display:grid;place-items:center;color:#fff;font-weight:700}
.nm{font-weight:700;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.tag{font-size:12px;font-weight:600;border-radius:999px;padding:1px 8px;background:var(--brand-soft);color:var(--brand)}
.tag.complaint{background:#fde8e8;color:var(--red)}.tag.suggestion{background:#ece9fb;color:var(--violet)}.tag.interested{background:#fdf1dc;color:var(--amber)}
.ph{color:var(--muted);font-size:14px;margin-top:2px}.sm{margin-top:4px}
.act{display:flex;flex-direction:column;align-items:flex-end;gap:8px}
.time{color:var(--muted);font-size:13px}
.btns{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}
.b{border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:10px;padding:8px 12px;font-weight:600;cursor:pointer;font-size:14px;text-decoration:none}
.b.go{background:var(--brand);border-color:var(--brand);color:#fff}
.st{font-size:13px;padding:6px 8px;border:1px solid var(--line);border-radius:10px;background:var(--card);color:var(--ink)}
.empty{color:var(--muted);text-align:center;padding:40px}
#toast{position:fixed;left:50%;bottom:24px;transform:translateX(-50%);background:#111;color:#fff;padding:12px 20px;border-radius:12px;display:none}
@media (max-width:640px){.item{grid-template-columns:40px 1fr}.act{grid-column:1/-1;align-items:stretch}.btns{justify-content:stretch}.b{flex:1;text-align:center}}
</style></head><body><div class="wrap">
<h1>Zayavkalar</h1><p class="sub">Potensial mijozlar, e'tirozlar va takliflar — AI suhbatlardan ajratadi · <a href="/api/chat/">Dialoglar →</a></p>
<div class="cards" id="cards"></div>
<div class="bar"><input id="q" placeholder="Ism, telefon yoki matn…" autocomplete="off">
<select id="status"><option value="">Barcha holatlar</option></select>
<select id="contact"><option value="">Har qanday kontakt</option><option value="yes">Telefon bor</option><option value="no">Telefonsiz</option></select></div>
<div class="list" id="list"><p class="empty">Yuklanmoqda…</p></div>
</div><div id="toast"></div>
<script>
const $=id=>document.getElementById(id);
const ICON={lead:['💼','#e6f4ec'],interested:['⭐','#fdf1dc'],complaint:['🛡','#fde8e8'],suggestion:['⚡','#ece9fb']};
const LABEL={lead:'Zayavkalar',interested:'Qiziqqan mijozlar',complaint:"E'tiroz va shikoyatlar",suggestion:'Takliflar'};
const COLORS=['#6366f1','#0ea5e9','#10b981','#f59e0b','#ec4899','#8b5cf6','#14b8a6'];
let category='lead',statuses={},categories={};
function toast(m){const t=$('toast');t.textContent=m;t.style.display='block';setTimeout(()=>t.style.display='none',2500)}
async function api(path,body){const r=await fetch(path,{method:body?'POST':'GET',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});
 if(r.status===401){location.href='/api/auth/telegram/login';throw 0}
 const d=await r.json().catch(()=>({}));if(!r.ok){toast(typeof d.detail==='string'?d.detail:'Xatolik');throw 0}return d}
function el(tag,cls,text){const e=document.createElement(tag);if(cls)e.className=cls;if(text!=null)e.textContent=text;return e}
function initials(n){const p=(n||'?').trim().split(/\\s+/);return((p[0]||'?')[0]+(p[1]?p[1][0]:'')).toUpperCase()}
function mask(p){return p?p.slice(0,7)+' • • • • • '+p.slice(-2):''}
function ago(ts){const s=Date.now()/1000-ts;if(s<3600)return Math.max(1,Math.floor(s/60))+' daq';if(s<86400)return Math.floor(s/3600)+' soat';return Math.floor(s/86400)+' kun'}
function dayLabel(ts){const d=new Date(ts*1000),t=new Date(),y=new Date(t);y.setDate(t.getDate()-1);
 if(d.toDateString()===t.toDateString())return 'Bugun';if(d.toDateString()===y.toDateString())return 'Kecha';return d.toLocaleDateString('uz-UZ',{day:'numeric',month:'long'})}
function cards(counts){const c=$('cards');c.replaceChildren();
 Object.keys(LABEL).forEach(k=>{const b=el('button','card'+(k===category?' on':''));const top=el('div','top');const i=el('div','ico',ICON[k][0]);i.style.background=ICON[k][1];
  top.append(i);if(counts[k].open)top.append(el('span','pill',counts[k].open+' yangi'));
  b.append(top,el('div','num',counts[k].total),el('div','lbl',LABEL[k]));b.onclick=()=>{category=k;load()};c.append(b)})}
function row(r){const it=el('div','item');const av=el('div','av',initials(r.name||'?'));av.style.background=COLORS[r.dialog_id%COLORS.length];
 const mid=el('div');const nm=el('div','nm');nm.append(document.createTextNode(r.name||(r.channel==='telegram'?'Telegram mijoz':'Instagram mijoz')),el('span','tag '+r.category,categories[r.category]));
 if(r.amocrm_lead_id)nm.append(el('span','tag','amoCRM #'+r.amocrm_lead_id));
 mid.append(nm);if(r.phone)mid.append(el('div','ph',mask(r.phone)));mid.append(el('div','sm',r.summary));
 const act=el('div','act');act.append(el('div','time',ago(r.created_at)));const btns=el('div','btns');
 const sel=el('select','st');Object.entries(statuses).forEach(([k,v])=>{const o=el('option',null,v);o.value=k;if(k===r.status)o.selected=true;sel.append(o)});
 sel.onchange=()=>setStatus(r.id,sel.value);
 btns.append(sel);if(r.status==='open'){const go=el('button','b go','✓ Ishga olish');go.onclick=()=>setStatus(r.id,'taken');btns.append(go)}
 const open=el('a','b','Dialog');open.href='/api/chat/?d='+r.dialog_id;btns.append(open);act.append(btns);it.append(av,mid,act);return it}
async function setStatus(id,status){try{await api('/api/chat/requests/'+id+'/status',{status})}catch(_){load().catch(()=>{});return}toast(statuses[status]+' ✓');load().catch(()=>{})}
async function load(){const p=new URLSearchParams({category,status:$('status').value,contact:$('contact').value,q:$('q').value});
 const d=await api('/api/chat/requests?'+p);statuses=d.statuses;categories=d.categories;
 const ss=$('status');if(ss.options.length===1)Object.entries(statuses).forEach(([k,v])=>{const o=el('option',null,v);o.value=k;ss.append(o)});
 cards(d.counts);const list=$('list');list.replaceChildren();
 if(!d.requests.length){list.append(el('p','empty','Hozircha zayavka yo\\'q'));return}
 let last='';d.requests.forEach(r=>{const dl=dayLabel(r.created_at);if(dl!==last){const day=el('div','day');day.append(el('span',null,dl));list.append(day);last=dl}list.append(row(r))})}
let qt;$('q').oninput=()=>{clearTimeout(qt);qt=setTimeout(()=>load().catch(()=>{}),300)};
$('status').onchange=$('contact').onchange=()=>load().catch(()=>{});
load().catch(()=>{});setInterval(()=>load().catch(()=>{}),30000);
</script></body></html>"""

"""Sozlamalar sahifasi HTML'i (`/api/chat/sozlamalar`) — docs/reveo-clone-spec.md 3.5.

Agent sozlamalari, bilimlar bazasi, instruksiya ko'rinishi va Testlash.
"""

PAGE = """<!doctype html>
<html lang="uz"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sozlamalar</title>
<style>
:root{--bg:#f4f6f5;--card:#fff;--ink:#14181a;--muted:#6b7378;--line:#e3e7e5;--brand:#2f9e6b;--brand-soft:#e6f4ec;--red:#dc2626;--track:#e3e7e5}
@media (prefers-color-scheme:dark){:root{--bg:#101314;--card:#1a1e20;--ink:#eef1f0;--muted:#9aa3a7;--line:#2a3033;--brand-soft:#173326;--track:#2a3033}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:20px 16px 60px;display:grid;grid-template-columns:200px 1fr;gap:20px}
nav{position:sticky;top:16px;align-self:start}nav h1{font-size:22px;margin:0 0 4px}nav .sub{color:var(--muted);font-size:13px;margin:0 0 14px}
nav a{display:block;padding:9px 12px;border-radius:10px;color:var(--ink);text-decoration:none;font-weight:600}nav a:hover{background:var(--card)}
nav .links{margin-top:14px;border-top:1px solid var(--line);padding-top:10px}nav .links a{font-weight:500;color:var(--brand)}
section{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:20px;margin-bottom:16px;scroll-margin-top:16px}
h2{font-size:18px;margin:0 0 2px}.hint{color:var(--muted);font-size:13px;margin:0 0 16px}
h3{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin:20px 0 10px}
.toggle{display:flex;align-items:center;gap:14px;padding:12px 0;border-bottom:1px solid var(--line)}.toggle:last-of-type{border-bottom:0}
.toggle .t{flex:1}.toggle b{display:block}.toggle span{color:var(--muted);font-size:13px}
.sw{position:relative;width:48px;height:28px;flex:none}.sw input{opacity:0;width:0;height:0}
.sw i{position:absolute;inset:0;background:var(--track);border-radius:999px;cursor:pointer;transition:.15s}
.sw i:before{content:"";position:absolute;width:22px;height:22px;left:3px;top:3px;background:#fff;border-radius:50%;transition:.15s;box-shadow:0 1px 2px rgba(0,0,0,.2)}
.sw input:checked+i{background:var(--brand)}.sw input:checked+i:before{transform:translateX(20px)}
.sw input:disabled+i{opacity:.45;cursor:not-allowed}
.g2{display:grid;grid-template-columns:1fr 1fr;gap:14px}
label{display:block;font-weight:600;margin-bottom:6px}
select,input[type=number],input[type=text],textarea{width:100%;padding:10px 12px;border:1px solid var(--line);border-radius:10px;background:var(--bg);color:var(--ink);font:inherit}
textarea{resize:vertical;min-height:76px}
input[type=range]{width:100%;accent-color:var(--brand)}.rl{color:var(--muted);font-size:12px}
.btn{border:0;border-radius:10px;padding:10px 16px;font-weight:700;cursor:pointer;font:inherit;font-weight:700}
.btn.go{background:var(--brand);color:#fff}.btn.ghost{background:var(--bg);color:var(--ink);border:1px solid var(--line)}.btn.del{background:none;color:var(--red);padding:6px 8px}
.save{position:sticky;bottom:12px;display:flex;justify-content:flex-end;gap:10px;align-items:center;margin-top:16px}
.save span{color:var(--muted);font-size:13px}
.kb{border:1px solid var(--line);border-radius:12px;padding:12px;margin-bottom:10px}.kb .row{display:flex;gap:8px;align-items:center}
.kb .row input{flex:1;font-weight:600}.kb textarea{margin-top:8px}
pre{white-space:pre-wrap;background:var(--bg);border:1px solid var(--line);border-radius:12px;padding:14px;font:13px/1.5 ui-monospace,monospace;max-height:340px;overflow:auto;margin:0}
.chat{display:flex;flex-direction:column;gap:8px;margin:12px 0;min-height:60px}
.m{max-width:80%;padding:9px 12px;border-radius:14px;white-space:pre-wrap}.m.in{align-self:flex-end;background:var(--brand);color:#fff}.m.out{align-self:flex-start;background:var(--bg);border:1px dashed #d4a72c}
.tr{display:flex;gap:8px}.tr input{flex:1}
.note{background:var(--brand-soft);border-radius:10px;padding:10px 12px;font-size:13px;margin-bottom:6px}
#toast{position:fixed;left:50%;bottom:24px;transform:translateX(-50%);background:#111;color:#fff;padding:12px 20px;border-radius:12px;display:none;z-index:9}
@media (max-width:820px){.wrap{grid-template-columns:1fr}nav{position:static}nav a{display:inline-block}.g2{grid-template-columns:1fr}}
</style></head><body><div class="wrap">
<nav><h1>Sozlamalar</h1><p class="sub">AI Chat Manager agenti</p>
<a href="#agent">Agent</a><a href="#script">Sotuv ssenariysi</a><a href="#kb">Bilimlar bazasi</a><a href="#test">Testlash</a><a href="#prompt">Instruksiya</a>
<div class="links"><a href="/api/chat/">Dialoglar</a><a href="/api/chat/zayavkalar">Zayavkalar</a><a href="/api/chat/analitika">Analitika</a></div></nav>
<main>
<section id="agent"><h2>Agent sozlamalari</h2><p class="hint">Agent mijozga qanday yozishi. AI faqat qoralama yozadi — yuborishni operator qiladi.</p>
<div class="note">Owner siyosati: AI mijozga hech qachon o'zi xabar yubormaydi. Avto-javob shu sababli o'chiq va qulflangan.</div>
<div class="toggle"><div class="t"><b>Avto-javoblar</b><span>Agent mijozga o'zi javob beradi</span></div><label class="sw"><input type="checkbox" id="auto_reply" disabled><i></i></label></div>
<div class="toggle"><div class="t"><b>Proaktiv dojimlar</b><span>Mijoz 24 soat jim qolsa, eslatma qoralamasi yoziladi (ko'pi bilan 2 marta)</span></div><label class="sw"><input type="checkbox" id="follow_ups"><i></i></label></div>
<div class="toggle"><div class="t"><b>Video tahlili</b><span>Yuborilgan videolarni tahlil qilish (sekinroq va qimmatroq)</span></div><label class="sw"><input type="checkbox" id="video_analysis"><i></i></label></div>
<h3>Temp va format</h3>
<div class="g2"><div><label for="messages_per_reply">Javobdagi xabarlar</label><select id="messages_per_reply"><option value="1">1 — bitta xabar</option><option value="2">2 — ikki xabar</option><option value="3">3 — uch xabar</option></select></div>
<div><label for="pause_before_reply_sec">Javobdan oldin pauza (sek)</label><input type="number" id="pause_before_reply_sec" min="0" max="60" step="1"></div>
<div><label for="pause_between_messages_sec">Xabarlar orasidagi pauza (sek)</label><input type="number" id="pause_between_messages_sec" min="0" max="10" step="0.1"></div></div>
<h3>Xarakter</h3>
<div class="g2"><div><label for="language">Muloqot tili</label><select id="language"><option value="uz">O'zbekcha</option><option value="ru">Ruscha</option><option value="en">Inglizcha</option></select></div>
<div><label for="agent_type">Agent turi</label><select id="agent_type"><option value="balanced">Muvozanatli</option><option value="sales">Faol sotuvchi</option><option value="support">Maslahatchi</option></select></div>
<div><label for="informativeness">Informativlik: <span id="informativeness_v"></span>/5</label><input type="range" id="informativeness" min="1" max="5"><div class="rl">1 — faqat savolga javob, 5 — faol tafsilot beradi</div></div>
<div><label for="reply_length">Javob uzunligi: <span id="reply_length_v"></span>/5</label><input type="range" id="reply_length" min="1" max="5"><div class="rl">1 — juda qisqa, 5 — batafsil</div></div></div></section>
<section id="script"><h2>Sotuv ssenariysi</h2><p class="hint">Agent maqsadi va qoidalari. Qat'iy cheklovlar har doim avtomatik qo'shiladi.</p>
<div class="g2"><div><label for="sales_goal">Asosiy sotuv maqsadi</label><textarea id="sales_goal" maxlength="2000"></textarea></div>
<div><label for="offer_rules">Offer va narx qoidalari</label><textarea id="offer_rules" maxlength="2000"></textarea></div>
<div><label for="qualification">Malakalash savollari</label><textarea id="qualification" maxlength="2000"></textarea></div>
<div><label for="handoff">Menejerga berish</label><textarea id="handoff" maxlength="2000"></textarea></div>
<div><label for="tone">Ton va uslub</label><textarea id="tone" maxlength="2000"></textarea></div></div>
<div class="save"><span id="dirty"></span><button class="btn go" id="saveBtn">Saqlash</button></div></section>
<section id="kb"><h2>Bilimlar bazasi</h2><p class="hint">Narxlar, xizmatlar, ish vaqti, FAQ. Agent faqat shu faktlarga tayanadi; bu yerda yo'q narsani menejerga beradi.</p>
<div id="kbList"></div><button class="btn ghost" id="kbAdd">+ Yozuv qo'shish</button></section>
<section id="test"><h2>Testlash</h2><p class="hint">Mijoz sifatida yozing — agent joriy sozlamalar bilan javob qoralamasini ko'rsatadi. Hech kimga yuborilmaydi. Avval saqlang.</p>
<div class="chat" id="chat"></div><form class="tr" id="testForm"><input type="text" id="testMsg" placeholder="Masalan: Logo narxi qancha?" maxlength="2000" autocomplete="off"><button class="btn go" type="submit" id="testBtn">Yuborish</button></form></section>
<section id="prompt"><h2>Instruksiya matni</h2><p class="hint">Sozlamalar va bilimlar bazasidan agentga beriladigan to'liq matn (faqat o'qish uchun).</p><pre id="instr"></pre></section>
</main></div><div id="toast"></div>
<script>
const $=id=>document.getElementById(id);
const BOOL=['follow_ups','video_analysis','auto_reply'],NUM=['messages_per_reply','pause_before_reply_sec','pause_between_messages_sec','informativeness','reply_length'],
 TXT=['language','agent_type','sales_goal','offer_rules','qualification','handoff','tone'];
let saved={};
function toast(m){const t=$('toast');t.textContent=m;t.style.display='block';setTimeout(()=>t.style.display='none',2500)}
async function api(path,method='GET',body){const r=await fetch(path,{method,credentials:'same-origin',headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});
 if(r.status===401){location.href='/api/auth/telegram/login';throw 0}
 const d=await r.json().catch(()=>({}));if(!r.ok){toast(typeof d.detail==='string'?d.detail:'Xatolik');throw 0}return d}
function el(tag,cls,text){const e=document.createElement(tag);if(cls)e.className=cls;if(text!=null)e.textContent=text;return e}
function fill(d){saved=d.settings;BOOL.forEach(k=>$(k).checked=!!saved[k]);NUM.forEach(k=>$(k).value=saved[k]);TXT.forEach(k=>$(k).value=saved[k]);
 ['informativeness','reply_length'].forEach(k=>$(k+'_v').textContent=saved[k]);$('instr').textContent=d.instructions;$('dirty').textContent=''}
function collect(){const out={};BOOL.filter(k=>k!=='auto_reply').forEach(k=>{if($(k).checked!==!!saved[k])out[k]=$(k).checked});
 NUM.forEach(k=>{const v=Number($(k).value);if(v!==saved[k])out[k]=v});TXT.forEach(k=>{if($(k).value.trim()!==saved[k])out[k]=$(k).value});return out}
function mark(){const n=Object.keys(collect()).length;$('dirty').textContent=n?n+' ta o\\'zgarish saqlanmagan':''}
document.querySelectorAll('input,select,textarea').forEach(e=>{if(e.closest('#kb')||e.closest('#test'))return;e.addEventListener('input',()=>{
 if(e.type==='range')$(e.id+'_v').textContent=e.value;mark()})});
['follow_ups','video_analysis'].forEach(k=>$(k).addEventListener('change',async()=>{try{const d=await api('/api/chat/settings','PUT',{[k]:$(k).checked});
 saved[k]=d.settings[k];$('instr').textContent=d.instructions;mark();toast('Saqlandi ✓')}catch(_){$(k).checked=!!saved[k]}}));
$('saveBtn').onclick=async()=>{const ch=collect();if(!Object.keys(ch).length){toast('O\\'zgarish yo\\'q');return}
 try{fill(await api('/api/chat/settings','PUT',ch));toast('Saqlandi ✓')}catch(_){}};
function kbItem(e){const box=el('div','kb');const row=el('div','row');const t=el('input');t.type='text';t.value=e.title||'';t.placeholder='Sarlavha, masalan: Logo narxlari';t.maxLength=200;
 const save=el('button','btn ghost','Saqlash');const del=el('button','btn del','O\\'chirish');row.append(t,save,del);
 const b=el('textarea');b.value=e.body||'';b.placeholder='Faktlar: narx, muddat, shartlar…';b.maxLength=4000;box.append(row,b);
 save.onclick=async()=>{try{if(e.id)await api('/api/chat/knowledge/'+e.id,'PUT',{title:t.value,body:b.value});else await api('/api/chat/knowledge','POST',{title:t.value,body:b.value});toast('Saqlandi ✓');loadKb()}catch(_){}};
 del.onclick=async()=>{if(!e.id){box.remove();return}if(!confirm('Yozuv o\\'chirilsinmi?'))return;try{await api('/api/chat/knowledge/'+e.id,'DELETE');loadKb()}catch(_){}};return box}
$('kbAdd').onclick=()=>{const it=kbItem({});$('kbList').append(it);it.querySelector('input').focus()};
$('testForm').onsubmit=async ev=>{ev.preventDefault();const msg=$('testMsg').value.trim();if(!msg)return;const chat=$('chat');chat.append(el('div','m in',msg));$('testMsg').value='';
 $('testBtn').disabled=true;const wait=el('div','m out','…');chat.append(wait);try{const d=await api('/api/chat/test','POST',{message:msg});wait.textContent=d.reply||'(bo\\'sh javob)'}catch(_){wait.remove()}finally{$('testBtn').disabled=false}};
async function loadKb(){const [s,k]=await Promise.all([api('/api/chat/settings'),api('/api/chat/knowledge')]);
 $('instr').textContent=s.instructions;renderKb(k)}
async function loadAll(){const [s,k]=await Promise.all([api('/api/chat/settings'),api('/api/chat/knowledge')]);fill(s);renderKb(k)}
function renderKb(k){const list=$('kbList');list.replaceChildren();if(!k.entries.length)list.append(el('p','hint','Hozircha bo\\'sh. Narx va xizmatlarni qo\\'shing — aks holda agent narx so\\'ralganda menejerga beradi.'));
 k.entries.forEach(e=>list.append(kbItem(e)))}
loadAll().catch(()=>{});
</script></body></html>"""

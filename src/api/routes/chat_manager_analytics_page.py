"""Analitika sahifasi HTML'i (`/api/chat/analitika`) — docs/reveo-clone-spec.md 3.3.

Ma'lumot `/api/chat/analytics?days=&channel=` dan; grafiklar kutubxonasiz.
"""

PAGE = """<!doctype html>
<html lang="uz"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Analitika</title>
<style>
:root{--bg:#f4f6f5;--card:#fff;--ink:#14181a;--muted:#6b7378;--line:#e3e7e5;--brand:#2f9e6b;--brand-soft:#e6f4ec;--track:#edf0ee;--red:#c2410c;
--h0:#eef1ef;--h1:#cfe9da;--h2:#9fd3b5;--h3:#5fb488;--h4:#2f7d55}
@media (prefers-color-scheme:dark){:root{--bg:#101314;--card:#1a1e20;--ink:#eef1f0;--muted:#9aa3a7;--line:#2a3033;--brand-soft:#173326;--track:#252b2d;
--h0:#22282a;--h1:#1d4430;--h2:#256b47;--h3:#36985f;--h4:#6fd39a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:20px 16px 40px}
h1{font-size:24px;margin:0}.sub{color:var(--muted);margin:2px 0 16px}.sub a{color:var(--brand)}
.bar{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:16px}
.seg{display:inline-flex;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:3px}
.seg button{border:0;background:transparent;color:var(--muted);padding:7px 14px;border-radius:9px;font-weight:600;cursor:pointer;font:inherit}
.seg button.on{background:var(--brand-soft);color:var(--brand)}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin-bottom:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:16px}
.kv{font-size:30px;font-weight:800;line-height:1.1;font-variant-numeric:tabular-nums}.kl{font-weight:600;margin-top:4px}.ks{color:var(--muted);font-size:13px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px}
h2{font-size:17px;margin:0 0 2px}.hs{color:var(--muted);font-size:13px;margin:0 0 14px}
.step{margin-bottom:14px}.sr{display:flex;justify-content:space-between;gap:8px;font-weight:600}
.sr span:last-child{font-variant-numeric:tabular-nums}
.track{height:10px;background:var(--track);border-radius:999px;margin:6px 0 4px;overflow:hidden}.fill{height:100%;background:var(--brand);border-radius:999px}
.note{color:var(--muted);font-size:12px}.note b{color:var(--red);font-weight:600}
.stats{display:grid;grid-template-columns:1fr 1fr;gap:10px}.stat{border:1px solid var(--line);border-radius:12px;padding:12px}
.stat .kv{font-size:24px}
.cats .row{display:grid;grid-template-columns:150px 1fr 40px;gap:10px;align-items:center;margin-bottom:10px}
.cats .row span:last-child{text-align:right;font-variant-numeric:tabular-nums;font-weight:600}
.chart{display:flex;align-items:flex-end;gap:4px;height:160px;padding-top:8px}
.col{flex:1;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;height:100%;min-width:0}
.colb{width:100%;max-width:28px;background:var(--h2);border-radius:4px 4px 0 0;position:relative}
.colb i{position:absolute;left:0;right:0;bottom:0;background:var(--h4);border-radius:4px 4px 0 0}
.xl{font-size:11px;color:var(--muted);margin-top:4px;white-space:nowrap}
.legend{display:flex;gap:14px;font-size:12px;color:var(--muted);margin-top:8px;align-items:center}.dot{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:5px;vertical-align:-1px}
table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:8px 6px;border-bottom:1px solid var(--line);font-variant-numeric:tabular-nums}th{color:var(--muted);font-weight:600;font-size:13px}
.hm{display:grid;grid-template-columns:28px repeat(24,1fr);gap:3px;align-items:center}
.hm div{height:22px;border-radius:4px}.hm .lab{height:auto;font-size:12px;color:var(--muted);background:none}
.hm .hx{height:auto;font-size:11px;color:var(--muted);background:none;text-align:left}
.peak{display:inline-block;background:var(--brand-soft);color:var(--brand);border-radius:999px;padding:2px 10px;font-size:13px;font-weight:700;margin-left:8px}
.hfoot{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-top:10px;font-size:12px;color:var(--muted)}
.scale{display:flex;gap:3px;align-items:center}.scale i{width:14px;height:14px;border-radius:3px}
.empty{color:var(--muted);text-align:center;padding:24px}
@media (max-width:820px){.grid{grid-template-columns:1fr}.hm{grid-template-columns:24px repeat(24,1fr);gap:2px}.hm div{height:14px}.cats .row{grid-template-columns:110px 1fr 32px}}
</style></head><body><div class="wrap">
<h1>Analitika</h1><p class="sub">Dialoglar va zayavkalar ko'rsatkichlari · <a href="/api/chat/">Dialoglar</a> · <a href="/api/chat/zayavkalar">Zayavkalar</a></p>
<div class="bar"><div class="seg" id="days"></div><div class="seg" id="channel"></div></div>
<div id="root"><p class="empty">Yuklanmoqda…</p></div>
</div>
<script>
const $=id=>document.getElementById(id);
let days=7,channel='';
function el(tag,cls,text){const e=document.createElement(tag);if(cls)e.className=cls;if(text!=null)e.textContent=text;return e}
function seg(id,opts,cur,set){const s=$(id);s.replaceChildren();opts.forEach(([v,l])=>{const b=el('button',v===cur?'on':'',l);b.onclick=()=>{set(v);load()};s.append(b)})}
function kpi(v,l,s){const c=el('div','card');c.append(el('div','kv',v),el('div','kl',l),el('div','ks',s));return c}
function section(title,hint){const c=el('div','card');c.append(el('h2',null,title),el('p','hs',hint));return c}
async function load(){seg('days',[[7,'7 kun'],[14,'14 kun'],[30,'30 kun']],days,v=>days=v);
 seg('channel',[['','Barcha kanallar'],['telegram','Telegram'],['instagram','Instagram']],channel,v=>channel=v);
 const r=await fetch('/api/chat/analytics?days='+days+'&channel='+channel,{credentials:'same-origin'});
 if(r.status===401){location.href='/api/auth/telegram/login';return}
 const d=await r.json();const root=$('root');root.replaceChildren();const k=d.kpi;
 const kp=el('div','kpis');
 kp.append(kpi(k.dialogs,'Dialoglar',d.days+' kun'),kpi(k.interested,'Xarid qilmoqchi',k.interested_pct+'% dialoglardan'),
  kpi(k.leads,'Zayavkalar',k.leads_open+' tasi hali ishlanmagan'),kpi(k.conversion+'%','Konversiya','qiziqqanlardan zayavkaga'),
  kpi(k.ai_drafted_pct+'%','AI qoralama yozdi','dialoglar ulushi'),kpi(k.after_hours_pct+'%','Ish vaqtidan tashqari','19:00–9:00 va dam olish kunlari'));
 root.append(kp);
 const g1=el('div','grid');const fu=section('Sotuv voronkasi','Dialogda nechta odam har bosqichga yetdi');
 const top=Math.max(d.funnel[0].count,1);
 d.funnel.forEach((s,i)=>{const st=el('div','step');const sr=el('div','sr');sr.append(el('span',null,(i+1)+'. '+s.title),el('span',null,s.count+' · '+s.of_previous+'%'));
  const tr=el('div','track');const f=el('div','fill');f.style.width=(100*s.count/top)+'%';tr.append(f);st.append(sr,tr);
  if(i){const n=el('div','note',s.of_previous+'% oldingi bosqichdan ');if(s.lost){n.append(el('b',null,'−'+s.lost+' yetmadi'))}st.append(n)}fu.append(st)});
 const oc=section('Dialoglar qanday tugadi','Javob tezligi va javobsiz qolganlar');const o=d.outcomes;const sts=el('div','stats');
 [[o.operator,'Menejer ulandi'],[o.unanswered,'Javob kutmoqda'],[o.avg_reply_min==null?'—':o.avg_reply_min+' daq','O\\'rtacha javob tezligi'],[o.complaints,'Shikoyatlar']]
  .forEach(([v,l])=>{const s=el('div','stat');s.append(el('div','kv',v),el('div','ks',l));sts.append(s)});oc.append(sts);
 const cats=el('div','cats');cats.style.marginTop='16px';const cmax=Math.max(1,...d.categories.map(c=>c.count));
 d.categories.forEach(c=>{const row=el('div','row');const tr=el('div','track');const f=el('div','fill');f.style.width=(100*c.count/cmax)+'%';tr.append(f);
  row.append(el('span',null,c.title),tr,el('span',null,c.count));cats.append(row)});oc.append(cats);g1.append(fu,oc);root.append(g1);
 const g2=el('div','grid');const dl=section('Kunlar bo\\'yicha','Faol dialoglar va yangi zayavkalar');const ch=el('div','chart');
 const dmax=Math.max(1,...d.daily.map(x=>x.dialogs));const step=Math.ceil(d.daily.length/8);
 d.daily.forEach((x,i)=>{const c=el('div','col');const b=el('div','colb');b.style.height=(100*x.dialogs/dmax)+'%';b.title=x.date+': '+x.dialogs+' dialog, '+x.requests+' zayavka';
  const inner=el('i');inner.style.height=(x.dialogs?100*Math.min(x.requests,x.dialogs)/x.dialogs:0)+'%';b.append(inner);
  c.append(b,el('div','xl',i%step===0?x.date.slice(8)+'.'+x.date.slice(5,7):'\\u00a0'));ch.append(c)});
 const lg=el('div','legend');[['var(--h2)','Dialoglar'],['var(--h4)','Zayavkalar']].forEach(([c,l])=>{const s=el('span');const dt=el('span','dot');dt.style.background=c;s.append(dt,document.createTextNode(l));lg.append(s)});
 dl.append(ch,lg);
 const cht=section('Kanallar','Dialoglar va zayavkaga aylanish');
 if(d.channels.length){const t=el('table');const hr=el('tr');['Kanal','Dialog','Ulush','Zayavka','Konversiya'].forEach(h=>hr.append(el('th',null,h)));t.append(hr);
  d.channels.forEach(c=>{const tr=el('tr');[c.channel==='telegram'?'Telegram':'Instagram',c.dialogs,c.share+'%',c.leads,c.conversion+'%'].forEach(v=>tr.append(el('td',null,v)));t.append(tr)});cht.append(t)}
 else cht.append(el('p','empty','Bu davrda dialog yo\\'q'));
 g2.append(dl,cht);root.append(g2);
 const hm=d.heatmap;const hc=el('div','card');const h=el('h2',null,'Mijozlar qachon yozadi');if(hm.peak)h.append(el('span','peak','Cho\\'qqi: '+hm.peak.weekday+', '+String(hm.peak.hour).padStart(2,'0')+':00'));
 hc.append(h,el('p','hs','Kiruvchi xabarlar hafta kuni va soat bo\\'yicha, Toshkent vaqti'));
 const grid=el('div','hm');const hmax=Math.max(1,...hm.cells.flat());const lv=v=>v===0?0:Math.min(4,1+Math.floor(3*v/hmax));
 hm.cells.forEach((row,di)=>{grid.append(el('div','lab',hm.weekdays[di]));row.forEach((v,hr)=>{const c=el('div');c.style.background='var(--h'+lv(v)+')';c.title=hm.weekdays[di]+' '+String(hr).padStart(2,'0')+':00 — '+v+' xabar';grid.append(c)})});
 grid.append(el('div','hx',''));for(let hr=0;hr<24;hr++)grid.append(el('div','hx',hr%3===0?String(hr).padStart(2,'0'):''));
 const foot=el('div','hfoot');const sc=el('div','scale');sc.append(document.createTextNode('Kam '));for(let i=0;i<5;i++){const q=el('i');q.style.background='var(--h'+i+')';sc.append(q)}sc.append(document.createTextNode(' Ko\\'p'));
 foot.append(sc,el('span',null,hm.after_hours_pct+'% xabar 19:00–9:00 va dam olish kunlari keladi — menejerlar odatda yo\\'q payt'));hc.append(grid,foot);root.append(hc)}
load().catch(()=>{});
</script></body></html>"""

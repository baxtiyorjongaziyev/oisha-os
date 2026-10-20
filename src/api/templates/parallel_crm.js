"use strict";
const API = "/api/crm/parallel";
const $ = id => document.getElementById(id);
let data = null, selected = null, offset = 0, searchTimer, detailVersion = 0;
let pendingEdit = null;
const labels = {queued:"amoCRM’ga yuborish kutilmoqda",sending:"Yuborilmoqda",uncertain:"Natija noma’lum",
  conflict:"Tekshirish kerak",applied:"Tasdiqlandi",discarded:"Bekor qilindi"};
const reasons = {remote_changed:"amoCRM’da bitim o‘zgargan",readback_mismatch:"Qayta tekshiruvda farq bor",
  remote_deleted:"amoCRM’da o‘chirilgan",ambiguous_write_review_required:"Natijani tekshirib, qayta tahrirlang",
  write_outcome_unknown:"Aloqa uzilgan, qayta tekshiriladi",interrupted_write:"Yuborish vaqtida tizim to‘xtagan",
  quiet_hours_deferred:"07:00 dan keyin yuboriladi",remote_read_unavailable:"amoCRM bilan aloqa kutilmoqda"};
function el(tag, text, cls) { const node = document.createElement(tag); if(text !== undefined)node.textContent=text; if(cls)node.className=cls;return node; }
function time(value) {return value ? new Date(value*1000).toLocaleString("uz-UZ") : "Hali tekshirilmagan";}
function money(lead) {return lead.price === null || lead.price === undefined ? "Summa kiritilmagan" :
  Number(lead.price).toLocaleString("uz-UZ") + (data?.account?.currency ? " "+data.account.currency : " (valyuta noma’lum)");}
function ownerName(id) {return data.users.find(u=>u.id===id)?.name || "Mas’ul #"+id;}
function activeOp(id) {return data.operations.find(o=>o.lead_id===id && ["queued","sending","uncertain","conflict"].includes(o.state));}
async function request(path, options={}) {
  const response = await fetch(API+path, {cache:"no-store",credentials:"same-origin",...options,
    headers:{"Content-Type":"application/json","X-Oisha-CRM":"1",...options.headers}});
  const body = await response.json().catch(()=>({}));
  if(!response.ok)throw new Error(typeof body.detail==="string" ? body.detail : "So‘rov bajarilmadi ("+response.status+")");
  return body;
}
function error(message) { $("error").hidden=!message; $("error").textContent=message || ""; }
function options(node, items, placeholder) {
  const previous=node.value;
  node.replaceChildren(new Option(placeholder,""),...items.map(i=>new Option(i.name,String(i.id))));
  node.value=previous;
}
async function load() {
  try {
    const next=await request("/snapshot?offset="+offset+"&q="+encodeURIComponent($("search").value));
    data=next;
    options($("pipeline"),data.pipelines,"Barcha voronkalar");
    options($("seller"),data.users,"Barcha sotuvchilar");
    $("sync").hidden=!data.can_manage;
    const status=data.sync.state;
    const messages={ready:"amoCRM bilan oxirgi tekshiruv: "+time(data.leads_checked_at),
      partial:"Ma’lumotlar qismlab olinmoqda. Hozir yuklangan bitimlar ko‘rsatilgan.",
      never_synced:"Hali ma’lumot olinmagan. Sinxronlashni sozlash kerak.",
      unavailable:"amoCRM bilan aloqa uzilgan. Oxirgi yuklangan nusxa ko‘rsatilgan: "+time(data.leads_checked_at)};
    $("notice").textContent=!data.enabled ? "Sinxronlash hali yoqilmagan. Ma’lumotlar joriy deb hisoblanmaydi." :
      (messages[status] || "Sinxronlash tekshirilmoqda.");
    if(!data.writeback)$("notice").textContent+=" Hozir ko‘rish rejimi.";
    $("notice").className=status==="ready" && data.enabled ? "" : "warn";
    if(data.enabled && status==="ready" && (!data.sync.checked_at || Date.now()/1000-data.sync.checked_at>180)){
      $("notice").textContent="Tekshiruv eskirgan. Oxirgi yuklangan nusxa: "+time(data.leads_checked_at);
      $("notice").className="warn";
    }
    if(selected && pendingEdit){
      const op=data.operations.find(item=>item.id===pendingEdit.request_id);
      if(op)$("edit-status").textContent=labels[op.state]+(reasons[op.reason]?" — "+reasons[op.reason]:"");
    }
    $("prev").disabled=offset===0;
    $("next").disabled=offset+data.limit>=data.loaded_total;
    $("page").textContent=data.loaded_total ? (offset+1)+"–"+Math.min(offset+data.limit,data.loaded_total)+" / "+data.loaded_total : "Bitim yo‘q";
    renderBoard();renderOperations();error("");
  } catch(e) {
    error(e.message+" Oxirgi muvaffaqiyatli ko‘rinish saqlanib turibdi.");
    $("notice").textContent="CRM bilan aloqa uzildi. Ko‘rsatilgan ma’lumot joriyligi tasdiqlanmagan.";
    $("notice").className="warn";
  }
}
function renderBoard() {
  if(!data)return;
  const pipeline=$("pipeline").value, seller=$("seller").value;
  const leads=data.leads.filter(l=>(!pipeline || String(l.pipeline_id)===pipeline) &&
    (!seller || String(l.responsible_user_id)===seller) && !l.is_deleted);
  $("count").textContent=leads.length+" ta ko‘rsatilmoqda";
  const stages=[];
  for(const p of data.pipelines.filter(p=>!pipeline||String(p.id)===pipeline))
    for(const s of p._embedded?.statuses || [])
      stages.push({...s,pipeline_id:p.id,title:pipeline?s.name:p.name+" / "+s.name});
  const known=new Set(stages.map(s=>s.pipeline_id+":"+s.id));
  for(const l of leads)if(!known.has(l.pipeline_id+":"+l.status_id)){
    stages.push({id:l.status_id,pipeline_id:l.pipeline_id,title:"Bosqich #"+l.status_id});
    known.add(l.pipeline_id+":"+l.status_id);
  }
  const board=$("board");board.replaceChildren();
  if(!stages.length){board.append(el("p",data.enabled?"Hali bitim yoki voronka yuklanmagan.":"Sinxronlash yoqilgach bitimlar shu yerda ko‘rinadi.","empty"));return;}
  for(const stage of stages){
    const items=leads.filter(l=>l.pipeline_id===stage.pipeline_id&&l.status_id===stage.id);
    const col=el("section",undefined,"column"),head=el("div",undefined,"column-head");
    head.append(el("h2",stage.title),el("span",String(items.length)));col.append(head);
    for(const lead of items){
      const card=el("button",undefined,"lead-card");card.type="button";
      card.append(el("strong",lead.name),el("span",money(lead),"amount"));
      const meta=el("div",undefined,"card-meta");meta.append(el("span",ownerName(lead.responsible_user_id)),el("span","#"+lead.id));card.append(meta);
      const op=activeOp(lead.id);if(op)card.append(el("span",labels[op.state],"pending"));
      card.addEventListener("click",()=>openLead(lead.id));col.append(card);
    }
    if(!items.length)col.append(el("div","Bu sahifada bitim yo‘q","empty"));
    board.append(col);
  }
}
function renderOperations() {
  const root=$("operations");root.replaceChildren();
  if(!data.operations.length){root.append(el("p","Hozircha o‘zgarish yo‘q.","subtle"));return;}
  for(const op of data.operations){
    const row=el("div",undefined,"op"),link=el("button","#"+op.lead_id);
    link.onclick=()=>openLead(op.lead_id);row.append(link,el("span",time(op.changed_at),"subtle"));
    const text=labels[op.state] || op.state, reason=reasons[op.reason];
    row.append(el("span",text+(reason?" — "+reason:""),"op-state "+(op.state==="applied"?"op-ok":"op-error")));
    if(data.can_write && ["queued","conflict","uncertain"].includes(op.state)){
      const b=el("button","Bekor qilish");b.onclick=async()=>{b.disabled=true;try{
        await request("/operations/"+op.id+"/discard",{method:"POST"});await load();
      }catch(e){error(e.message);}finally{b.disabled=false;}};row.append(b);
    }
    root.append(row);
  }
}
function phones(contact) {return (contact.custom_fields_values || []).filter(f=>f.field_code==="PHONE")
  .flatMap(f=>f.values || []).map(v=>v.value).filter(Boolean);}
async function openLead(id) {
  const version=++detailVersion;
  try {
    const result=await request("/leads/"+id);
    if(version!==detailVersion)return;
    selected=result.lead;pendingEdit=null;
    $("lead-id").textContent="Bitim #"+id;$("name").value=selected.name;
    $("owner").value=ownerName(selected.responsible_user_id);$("price").textContent=money(selected);
    const stages=data.pipelines.find(p=>p.id===selected.pipeline_id)?._embedded?.statuses || [];
    $("stage").replaceChildren(...stages.map(s=>new Option(s.name,String(s.id))));
    $("stage").value=String(selected.status_id);
    const editable=data.writeback&&data.can_write&&!activeOp(id)&&!selected.is_deleted;
    $("name").readOnly=!editable;$("stage").disabled=!editable;$("save").disabled=!editable;
    $("edit-status").textContent=activeOp(id)?"Avval kutilayotgan o‘zgarish holatini tekshiring.":editable?
      "Saqlash amoCRM’dagi shu bitimni ham o‘zgartiradi.":"Hozir ko‘rish rejimi.";
    const contactRoot=$("contacts");contactRoot.replaceChildren();
    for(const c of result.contacts)contactRoot.append(el("div",(c.name || "Kontakt #"+c.id)+"\n"+(phones(c).join(", ")||"Telefon kiritilmagan"),"contact"));
    if(!result.contacts.length)contactRoot.append(el("p","Kontakt ma’lumoti hali yuklanmagan.","subtle"));
    const taskRoot=$("tasks");taskRoot.replaceChildren();
    for(const t of result.tasks)taskRoot.append(el("div",t.text+"\n"+(t.is_completed?"Bajarilgan":"Muddat: "+time(t.complete_till)),"task"));
    if(result.tasks_total>result.tasks.length)taskRoot.append(el("p",result.tasks.length+" / "+result.tasks_total+" ta vazifa ko‘rsatilgan. Qolgan tarix amoCRM’da.","subtle"));
    if(!result.tasks.length)taskRoot.append(el("p","Yuklangan nusxada vazifa yo‘q.","subtle"));
    $("source").hidden=true;
    // The configured account URL is supplied by the backend; never infer a subdomain.
    if(data.source_url){$("source").href=data.source_url+"/leads/detail/"+id;$("source").hidden=false;}
    $("notes").replaceChildren(el("p","Izohlar yuklanmoqda…","subtle"));
    if(!$("detail").open)$("detail").showModal();
    $("name").focus();
    try {
      const notes=await request("/leads/"+id+"/notes");
      if(version!==detailVersion)return;
      $("notes").replaceChildren(...notes.notes.map(n=>el("div",time(n.created_at)+"\n"+(n.text||"Hodisa: "+n.type),"note")));
      if(!notes.notes.length)$("notes").append(el("p","So‘nggi izohlar yo‘q.","subtle"));
    }catch(e){if(version===detailVersion)$("notes").replaceChildren(el("p",e.message,"subtle"));}
  }catch(e){error(e.message);}
}
$("edit").addEventListener("submit",async event=>{
  event.preventDefault();if(!selected)return;
  const patch={};
  if($("name").value!==selected.name)patch.name=$("name").value;
  if(Number($("stage").value)!==selected.status_id)patch.status_id=Number($("stage").value);
  if(!Object.keys(patch).length){$("edit-status").textContent="O‘zgarish kiritilmadi.";return;}
  const signature=JSON.stringify(patch);
  if(!pendingEdit || pendingEdit.signature!==signature)pendingEdit={signature,request_id:crypto.randomUUID()};
  $("save").disabled=true;
  try {
    const op=await request("/leads/"+selected.id,{method:"PATCH",body:JSON.stringify({
      request_id:pendingEdit.request_id,revision:selected.revision,patch})});
    $("edit-status").textContent=labels[op.state];$("name").readOnly=true;$("stage").disabled=true;await load();
  }catch(e){$("edit-status").textContent=e.message;$("save").disabled=false;}
});
$("detail").addEventListener("close",()=>{detailVersion++;selected=null;});
$("close").onclick=()=>$("detail").close();
$("pipeline").onchange=renderBoard;$("seller").onchange=renderBoard;
$("search").oninput=()=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>{offset=0;load();},300);};
$("prev").onclick=()=>{offset=Math.max(0,offset-200);load();};
$("next").onclick=()=>{offset+=200;load();};
$("sync").onclick=async()=>{ $("sync").disabled=true;try{await request("/sync",{method:"POST"});
  $("notice").textContent="Yangilash so‘raldi. Natija keyingi tekshiruvda ko‘rinadi.";
}catch(e){error(e.message);}finally{$("sync").disabled=false;}};
load();setInterval(()=>{if(!document.hidden)load();},15000);

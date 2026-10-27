// O'zbekcha amoCRM 1:1 — Real-time Caller ID Pop-up (MoiZvonki kiruvchi qo'ng'iroq ekrani)
// va amoCRM Enterprise: Rad etish (Closed Lost) sabablari boshqaruvi
let currentCallerIdLeadId = null;
let callerIdPollTimer = null;
let currentLossLeadId = null;

window.addEventListener("DOMContentLoaded", () => {
  startCallerIdPolling();
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      dismissCallerIdCard();
      closeLossModal();
    }
  });
});

function getCurrentRepSlug() {
  if (typeof getLoggedInSeller === "function") {
    const s = getLoggedInSeller();
    if (s && s.slug) return s.slug;
  }
  const urlRep = new URLSearchParams(window.location.search).get("rep");
  if (urlRep) return urlRep.toLowerCase();
  const selectVal = document.getElementById("repFilterSelect")?.value;
  const idMap = {
    "13021974": "shahnoza",
    "9000001": "rayxona",
    "13838466": "oydin",
    "9000002": "mumtozmaxal",
    "8128012": "baxtiyorjon",
  };
  return idMap[selectVal] || "shahnoza";
}

function startCallerIdPolling() {
  checkCallerId();
  if (!callerIdPollTimer) {
    callerIdPollTimer = setInterval(checkCallerId, 2000);
  }
}

async function checkCallerId() {
  const repSlug = getCurrentRepSlug();
  try {
    const res = await fetch(`/api/crm/dialer/caller-id/active?rep_slug=${encodeURIComponent(repSlug)}`);
    if (res.status === 401) {
      if (callerIdPollTimer) { clearInterval(callerIdPollTimer); callerIdPollTimer = null; }
      return;
    }
    const data = await res.json();
    if (data.active && data.call) {
      renderCallerIdCard(data.call);
    } else {
      document.getElementById("callerIdCard")?.classList.add("hidden");
    }
  } catch (err) {}
}

function renderCallerIdCard(call) {
  const card = document.getElementById("callerIdCard");
  if (!card) return;
  card.classList.remove("hidden");
  document.getElementById("callerIdPhone").innerText = typeof formatPhone === "function" ? formatPhone(call.phone) : call.phone;
  const lead = call.lead;
  if (lead) {
    currentCallerIdLeadId = lead.id;
    document.getElementById("callerIdName").innerText = lead.contact_name || lead.name;
    document.getElementById("callerIdCompany").innerText = lead.company_name || lead.name;
    document.getElementById("callerIdStage").innerText = lead.status_slug || "YANGI";
    document.getElementById("callerIdBudget").innerText = `${Number(lead.price || 0).toLocaleString("uz-UZ")} so'm`;
    document.getElementById("callerIdLeadBox")?.classList.remove("hidden");
    document.getElementById("callerIdOpenBtn").innerText = `Bitim #${lead.id} ni ochish →`;
  } else {
    currentCallerIdLeadId = null;
    document.getElementById("callerIdName").innerText = "Yangi raqam (Bazada yo'q)";
    document.getElementById("callerIdCompany").innerText = "MoiZvonki kiruvchi qo'ng'iroq";
    document.getElementById("callerIdLeadBox")?.classList.add("hidden");
    document.getElementById("callerIdOpenBtn").innerText = "+ Yangi bitim ochish";
  }
}

function openCallerIdLead() {
  dismissCallerIdCard();
  if (currentCallerIdLeadId && typeof openDealDrawer === "function") {
    openDealDrawer(currentCallerIdLeadId);
  } else if (typeof openNewDealModal === "function") {
    openNewDealModal();
    const phone = document.getElementById("callerIdPhone")?.innerText.replace(/\s+/g, "");
    const inp = document.getElementById("newDealPhone");
    if (inp && phone) inp.value = phone;
  }
}

async function dismissCallerIdCard() {
  const card = document.getElementById("callerIdCard");
  if (card) card.classList.add("hidden");
  const repSlug = getCurrentRepSlug();
  try {
    await fetch(`/api/crm/dialer/caller-id/dismiss?rep_slug=${encodeURIComponent(repSlug)}`, { method: "POST" });
  } catch (err) {}
}

// ==========================================
// amoCRM Enterprise: Rad etish (Closed Lost) Sabablari
// ==========================================

function openLossModal(leadId, targetSlug, stageTitle, price, name) {
  currentLossLeadId = leadId;
  const modal = document.getElementById("lossReasonModal");
  if (!modal) return;
  const leadIdEl = document.getElementById("lossLeadId");
  const leadNameEl = document.getElementById("lossLeadName");
  const amountEl = document.getElementById("lossAmountInput");
  const noteEl = document.getElementById("lossNoteInput");

  if (leadIdEl) leadIdEl.value = leadId;
  if (leadNameEl) leadNameEl.innerText = name ? `${name} (#${leadId})` : `#${leadId}`;
  if (amountEl) amountEl.value = price || 0;
  if (noteEl) noteEl.value = "";

  modal.classList.remove("hidden");
}

function closeLossModal() {
  const modal = document.getElementById("lossReasonModal");
  if (modal) modal.classList.add("hidden");
  currentLossLeadId = null;
}

async function submitLossRecord() {
  const leadId = parseInt(document.getElementById("lossLeadId")?.value || currentLossLeadId, 10);
  if (!leadId) {
    if (typeof showToast === "function") showToast("Bitim ID si aniqlanmadi");
    return;
  }
  const reason = document.getElementById("lossReasonSelect")?.value || "Boshqa sabab";
  const lostAmount = parseFloat(document.getElementById("lossAmountInput")?.value) || 0;
  const note = (document.getElementById("lossNoteInput")?.value || "").trim();
  const sellerName = typeof currentRepId !== "undefined" && currentRepId ? "Shahnoza Abdijabborova" : "Sotuvchi";

  try {
    const res = await fetch(`/api/crm/dialer/lead/${leadId}/loss`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        reason: reason,
        note: note,
        lost_amount: lostAmount,
        seller_name: sellerName,
      }),
    });
    const d = await res.json();
    if (d.success) {
      if (typeof showToast === "function") showToast(`Sdelka rad etildi: ${reason}`);
      closeLossModal();
      if (typeof closeDealDrawer === "function") closeDealDrawer();
      if (typeof fetchKanban === "function") await fetchKanban();
    } else {
      if (typeof showToast === "function") showToast("Rad etishni saqlashda xatolik");
    }
  } catch (err) {
    console.error("Loss record error:", err);
    if (typeof showToast === "function") showToast("Serverga ulanishda xatolik yuz berdi");
  }
}

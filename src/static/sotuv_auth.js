// O'zbekcha amoCRM 1:1 — Haqiqiy Server-Auth Sotuvchilar Kirishi (PIN-kod Serverda Tekshiriladi)
let activeAuthSellers = [];
let selectedLoginSlug = "shahnoza";

window.addEventListener("DOMContentLoaded", async () => {
  ensureAuthModalDom();
  await loadSellersList();
  await checkAndEnforceSellerAuth();
});

async function loadSellersList() {
  try {
    const res = await fetch("/api/crm/dialer/auth/sellers");
    const data = await res.json();
    if (data.sellers && data.sellers.length > 0) {
      activeAuthSellers = data.sellers;
      renderSellerCardsInModal();
    }
  } catch (e) {
    console.error("Sellers fetch error:", e);
  }
}

function getLoggedInSeller() {
  try {
    const raw = localStorage.getItem("jon_crm_seller_session");
    if (!raw) return null;
    return JSON.parse(raw);
  } catch (e) {
    return null;
  }
}

async function checkAndEnforceSellerAuth() {
  const seller = getLoggedInSeller();
  if (seller && seller.slug) {
    // Serverda sessiya yaroqliligini tekshirish
    try {
      const res = await fetch("/api/crm/dialer/auth/me");
      if (res.ok) {
        const data = await res.json();
        applySellerSession(data.seller || seller);
        return;
      }
    } catch (e) {}
  }
  showSellerLoginModal();
}

function applySellerSession(seller) {
  if (typeof currentRepId !== "undefined") currentRepId = String(seller.rep_id);
  const repSelect = document.getElementById("repFilterSelect");
  if (repSelect) repSelect.value = String(seller.rep_id);
  updateHeaderSellerBadge(seller);
  const modal = document.getElementById("sellerLoginModal");
  if (modal) modal.classList.add("hidden");
  if (typeof fetchKanban === "function") fetchKanban();
}

function updateHeaderSellerBadge(seller) {
  let badge = document.getElementById("headerSellerAuthBadge");
  if (!badge) {
    const headerRight = document.querySelector("#amoTopHeader > div:last-child");
    if (headerRight) {
      badge = document.createElement("div");
      badge.id = "headerSellerAuthBadge";
      badge.className = "flex items-center gap-2 px-3 py-1.5 rounded-full bg-[#f1f5f9] border border-[#e2e8f0]";
      headerRight.insertBefore(badge, headerRight.firstChild);
    }
  }
  if (badge && seller) {
    const roleBadge = seller.role === "admin" ? "bg-[#fef3c7] text-[#b45309]" : "bg-[#dbeafe] text-[#1d4ed8]";
    badge.innerHTML = `
      <span class="flex items-center justify-center">${seller.role === "admin" ? `<svg class="w-4 h-4 inline-block text-amber-500 shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><rect x="3" y="11" width="18" height="11" rx="2"/><path stroke-linecap="round" stroke-linejoin="round" d="M7 11V7a5 5 0 0110 0v4"/></svg>` : `<svg class="w-4 h-4 inline-block text-sky-500 shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg>`}</span>
      <div class="flex flex-col text-left leading-none">
        <span class="text-xs font-bold text-[#1e293b]">${seller.name}</span>
        <span class="text-[10px] text-[#64748b] font-medium">${seller.tg || seller.phone}</span>
      </div>
      <span class="text-[10px] px-1.5 py-0.5 rounded font-bold ${roleBadge} uppercase">${seller.role}</span>
      <button onclick="logoutSeller()" class="ml-1 text-[11px] text-[#ef4444] hover:underline font-bold" title="Chiqish">Chiqish</button>
    `;
  }
}

function showSellerLoginModal() {
  const modal = document.getElementById("sellerLoginModal");
  if (modal) {
    modal.classList.remove("hidden");
    renderSellerCardsInModal();
    const pinInp = document.getElementById("sellerPinInput");
    if (pinInp) {
      pinInp.value = "";
      setTimeout(() => pinInp.focus(), 150);
    }
  }
}

function selectSellerForLogin(slug) {
  selectedLoginSlug = slug;
  renderSellerCardsInModal();
  const errEl = document.getElementById("sellerLoginError");
  if (errEl) errEl.classList.add("hidden");
  const pinInp = document.getElementById("sellerPinInput");
  if (pinInp) {
    pinInp.value = "";
    pinInp.focus();
  }
}

function renderSellerCardsInModal() {
  const container = document.getElementById("modalSellersGrid");
  if (!container) return;
  const list = activeAuthSellers.length > 0 ? activeAuthSellers : [
    { slug: "shahnoza", name: "Shahnoza Abdijabborova", phone: "+998773220042", tg: "@jonbranding_assistant" },
    { slug: "rayxona", name: "Rayxona Rahimova", phone: "+998777411397", tg: "@RayxonJonbranding" },
    { slug: "mumtozmaxal", name: "Mumtozmaxal Normurodova", phone: "+998773220098", tg: "@MumtozmaxalJonbranding" },
    { slug: "hasanboy", name: "Hasanboy Gaziyev", phone: "+998973355900", tg: "@hasan_yahyo", role: "specialist" },
    { slug: "baxtiyorjon", name: "Baxtiyorjon Gaziyev", phone: "+998336450097", tg: "@baxtiyorjongaziyev", role: "admin" },
  ];
  container.innerHTML = list.map((s) => {
    const isSel = s.slug === selectedLoginSlug;
    const icon = s.role === "admin" ? `<svg class="w-4 h-4 inline-block text-amber-500 shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><rect x="3" y="11" width="18" height="11" rx="2"/><path stroke-linecap="round" stroke-linejoin="round" d="M7 11V7a5 5 0 0110 0v4"/></svg>` : `<svg class="w-4 h-4 inline-block text-sky-500 shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg>`;
    const subLabel = s.phone ? (s.tg ? `${s.phone} · ${s.tg}` : s.phone) : (s.tg || "Sotuvchi");
    return `
      <div onclick="selectSellerForLogin('${s.slug}')" class="p-2.5 rounded-lg border-2 cursor-pointer transition flex items-center gap-2.5 ${isSel ? "border-[#4c8bf7] bg-[#eff6ff] shadow-sm" : "border-[#e2e8f0] bg-white hover:border-[#cbd5e1]"}">
        <span class="text-2xl">${icon}</span>
        <div class="flex flex-col min-w-0 text-left">
          <span class="text-xs font-bold text-[#1e293b] truncate">${s.name}</span>
          <span class="text-[11px] text-[#64748b] truncate font-mono">${subLabel}</span>
        </div>
        ${isSel ? '<span class="ml-auto text-xs font-bold text-[#3875d7] flex items-center"><svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg></span>' : ""}
      </div>
    `;
  }).join("");
}

async function submitSellerLogin() {
  const pinInp = document.getElementById("sellerPinInput");
  const enteredPin = pinInp ? pinInp.value.trim() : "";
  const errEl = document.getElementById("sellerLoginError");
  if (!enteredPin) {
    if (errEl) { errEl.innerText = "PIN-kodni kiriting!"; errEl.classList.remove("hidden"); }
    return;
  }

  try {
    const res = await fetch("/api/crm/dialer/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ slug: selectedLoginSlug, pin: enteredPin }),
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      if (errEl) {
        errEl.innerText = errData.detail || "Noto'g'ri PIN-kod!";
        errEl.classList.remove("hidden");
      }
      return;
    }

    const data = await res.json();
    localStorage.setItem("jon_crm_seller_session", JSON.stringify(data.seller));
    if (data.token) localStorage.setItem("jon_crm_token", data.token);
    if (typeof showToast === "function") showToast(`Xush kelibsiz, ${data.seller.name}!`);
    applySellerSession(data.seller);
  } catch (err) {
    if (errEl) {
      errEl.innerText = "Serverga ulanishda xatolik yuz berdi!";
      errEl.classList.remove("hidden");
    }
  }
}

async function logoutSeller() {
  try {
    await fetch("/api/crm/dialer/auth/logout", { method: "POST" });
  } catch (e) {}
  localStorage.removeItem("jon_crm_seller_session");
  localStorage.removeItem("jon_crm_token");
  const badge = document.getElementById("headerSellerAuthBadge");
  if (badge) badge.remove();
  if (typeof showToast === "function") showToast("Tizimdan chiqildi");
  showSellerLoginModal();
}

function ensureAuthModalDom() {
  if (document.getElementById("sellerLoginModal")) return;
  const div = document.createElement("div");
  div.id = "sellerLoginModal";
  div.className = "fixed inset-0 bg-slate-900/85 backdrop-blur-md z-[9999] flex items-center justify-center p-4";
  div.innerHTML = `
    <div class="bg-white rounded-2xl shadow-2xl w-full max-w-lg p-6 flex flex-col gap-4 border border-[#e2e8f0]">
      <div class="text-center pb-2 border-b border-[#f1f5f9]">
        <div class="w-12 h-12 rounded-full bg-gradient-to-tr from-[#0284c7] to-[#38bdf8] text-white text-xl font-bold flex items-center justify-center mx-auto mb-2 shadow-md">JB</div>
        <h2 class="text-xl font-bold text-[#0f172a]">Jon CRM — Xavfsiz Kirish</h2>
        <p class="text-xs text-[#64748b] mt-1">Shaxsiy profilingizni tanlang va maxfiy PIN-kodingizni kiriting.</p>
      </div>
      <div>
        <label class="block text-xs font-bold uppercase tracking-wider text-[#64748b] mb-2">1. Xodimni tanlang:</label>
        <div id="modalSellersGrid" class="grid grid-cols-2 gap-2"></div>
      </div>
      <div class="pt-1">
        <label class="block text-xs font-bold uppercase tracking-wider text-[#64748b] mb-1.5">2. Maxfiy PIN-kod:</label>
        <div class="flex items-center gap-2">
          <input id="sellerPinInput" type="password" maxlength="8" placeholder="••••" onkeydown="if(event.key==='Enter') submitSellerLogin()" class="flex-1 text-center font-mono text-2xl tracking-widest p-2.5 border-2 border-[#cbd5e1] rounded-lg focus:outline-none focus:border-[#4c8bf7] bg-[#f8fafc]">
          <button onclick="submitSellerLogin()" class="px-6 py-3 bg-[#4c8bf7] hover:bg-[#3b78e7] text-white font-bold text-sm rounded-lg shadow-md transition shrink-0">KIRISH →</button>
        </div>
        <div id="sellerLoginError" class="hidden text-xs text-[#ef4444] font-semibold mt-1.5 text-center"></div>
      </div>
      <div class="text-center pt-2 border-t border-[#f1f5f9] text-[11px] text-[#94a3b8]">
        <span class="flex items-center gap-1.5 justify-center"><svg class="w-3.5 h-3.5 text-[#7e8b9b]" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><rect x="3" y="11" width="18" height="11" rx="2"/><path stroke-linecap="round" stroke-linejoin="round" d="M7 11V7a5 5 0 0110 0v4"/></svg><span>Tizim PBKDF2-SHA256 xavfsiz shifrlash bilan himoyalangan</span></span>
      </div>
    </div>
  `;
  document.body.appendChild(div);
}

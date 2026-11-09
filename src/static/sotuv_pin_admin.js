// Administrator: xodim PIN-kodini tiklash. Vaqtinchalik PIN faqat bir marta koʻrsatiladi;
// xodim birinchi kirishda uni oʻz PIN-kodiga almashtiradi.
const PIN_STATUS_LABELS = {
  active: "Faol",
  change_required: "Almashtirishi kerak",
  locked: "Qulflangan",
};

function pinAdminEl(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

async function resetSellerPin(seller, resultBox, button) {
  if (!/^[a-z0-9_-]{1,50}$/.test(String(seller.slug))) {
    resultBox.textContent = "Notoʻgʻri xodim identifikatori.";
    return;
  }
  if (!window.confirm(`${seller.name}: eski PIN va barcha sessiyalar bekor qilinadi. Davom etasizmi?`)) return;
  button.disabled = true;
  resultBox.textContent = "";
  try {
    const res = await fetch("/api/crm/dialer/auth/admin/reset-pin", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ slug: seller.slug }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      resultBox.textContent = (data.detail && (data.detail.message || data.detail)) || "PIN-kodni tiklab boʻlmadi.";
      resultBox.className = "text-xs font-semibold text-[#ef4444]";
      return;
    }
    resultBox.className = "text-xs font-semibold text-[#0f172a]";
    resultBox.append("Vaqtinchalik PIN: ", pinAdminEl("code", "font-mono font-bold text-sm", data.temp_pin));
    resultBox.append(" (faqat hozir koʻrinadi, xodimga shaxsan yuboring)");
  } catch {
    resultBox.textContent = "Serverga ulanishda xatolik yuz berdi!";
    resultBox.className = "text-xs font-semibold text-[#ef4444]";
  } finally {
    button.disabled = false;
  }
}

function sellerPinRow(seller) {
  const row = pinAdminEl("div", "p-3 border-b border-[#eef2f5] last:border-0 flex flex-col gap-1.5");
  const line = pinAdminEl("div", "flex items-center justify-between gap-3");
  const info = pinAdminEl("div", "flex flex-col min-w-0");
  info.append(
    pinAdminEl("span", "text-sm font-bold text-[#1565c0] truncate", seller.name),
    pinAdminEl("span", "text-xs text-[#64748b]", `PIN holati: ${PIN_STATUS_LABELS[seller.pin_status] || seller.pin_status}`),
  );
  const button = pinAdminEl("button", "px-3 py-1.5 text-xs font-bold rounded border border-[#cbd5e1] text-[#334155] hover:bg-[#f1f5f9] disabled:opacity-50 shrink-0", "PIN tiklash");
  button.type = "button";
  const resultBox = pinAdminEl("div", "text-xs");
  button.addEventListener("click", () => resetSellerPin(seller, resultBox, button));
  line.append(info, button);
  row.append(line, resultBox);
  return row;
}

async function renderSellerPinAdmin() {
  const box = document.getElementById("sellerPinAdminBox");
  if (!box) return;
  const res = await fetch("/api/crm/dialer/auth/admin/sellers");
  if (!res.ok) return; // faqat Administrator koʻradi
  const data = await res.json();
  const card = pinAdminEl("div", "bg-white rounded border border-[#e5e7eb] overflow-hidden shadow-sm");
  card.append(pinAdminEl("div", "p-4 border-b border-[#e5e7eb] font-bold text-base uppercase text-[#2e3640]", "Xodimlar PIN-kodi"));
  (data.sellers || []).forEach((seller) => card.append(sellerPinRow(seller)));
  box.replaceChildren(card);
}

window.renderSellerPinAdmin = renderSellerPinAdmin;

// Jon CRM — 1-Click MoiZvonki Callback va Interaktiv Audio Pleyer & Whisper STT Tizimi
let currentPlayingAudio = null;
const _escCall = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const _posCallInt = (v) => { const s = String(v ?? "").trim(); const n = /^\d+$/.test(s) ? Number(s) : 0; return Number.isSafeInteger(n) && n > 0 ? n : 0; };

function getCrmAuthToken() {
  try {
    const raw = localStorage.getItem("jon_crm_seller_session");
    if (!raw) return "";
    const sess = JSON.parse(raw);
    return (sess && sess.token) ? sess.token : "";
  } catch (e) {
    return "";
  }
}

async function trigger1ClickCall(leadId, clientPhone) {
  if (!clientPhone) {
    if (typeof showToast === "function") showToast("⚠️ Mijoz telefon raqami topilmadi");
    return;
  }

  const seller = (typeof getLoggedInSeller === "function") ? getLoggedInSeller() : null;
  const sellerSlug = seller ? seller.slug : "shahnoza";
  const sellerName = seller ? seller.name : "Sotuvchi";

  if (typeof showToast === "function") {
    showToast(`📞 1-Click Qo'ng'iroq: ${sellerName} ➔ ${clientPhone}...`);
  }

  try {
    const token = getCrmAuthToken();
    const headers = { "Content-Type": "application/json" };
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
      headers["X-CRM-Session-Token"] = token;
    }

    const res = await fetch("/api/crm/dialer/calls/callback", {
      method: "POST",
      headers: headers,
      body: JSON.stringify({
        lead_id: parseInt(leadId, 10),
        client_phone: clientPhone,
        seller_slug: sellerSlug,
      }),
    });

    const data = await res.json();
    if (res.ok && data.success) {
      if (typeof showToast === "function") {
        showToast(data.message || `✅ Qo'ng'iroq ulandi! Telefoningizni kuting (${data.seller_phone})`);
      }
      if (data.tel_url && /^tel:\+?\d{5,15}$/.test(String(data.tel_url)) && window.innerWidth < 768) {
        window.location.href = String(data.tel_url);
      }
      if (typeof loadLeadCallHistory === "function") {
        const safeCallbackLeadId = _posCallInt(leadId);
        if (safeCallbackLeadId) {
          setTimeout(() => loadLeadCallHistory(safeCallbackLeadId), 1500);
        }
      }
    } else {
      if (typeof showToast === "function") {
        showToast(`❌ Qo'ng'iroq xatosi: ${data.detail || data.message || "Ulab bo'lmadi"}`);
      }
    }
  } catch (err) {
    console.error("Callback trigger error:", err);
    if (typeof showToast === "function") showToast("⚠️ Qo'ng'iroq so'rovida tarmoq xatoligi");
  }
}

async function loadLeadCallHistory(leadId) {
  const container = document.getElementById("drawerCallsHistoryBox");
  const safeLeadId = _posCallInt(leadId);
  if (!container || !safeLeadId) return;

  try {
    const token = getCrmAuthToken();
    const headers = {};
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
      headers["X-CRM-Session-Token"] = token;
    }

    const res = await fetch(`/api/crm/dialer/calls/history/${safeLeadId}`, { headers: headers });
    if (!res.ok) return;
    const data = await res.json();
    if (data.success && Array.isArray(data.calls) && data.calls.length > 0) {
      container.classList.remove("hidden");
      container.innerHTML = `
        <div class="flex items-center justify-between pb-2 mb-2 border-b border-[#e2e8f0]">
          <span class="text-xs font-bold text-[#1e293b] flex items-center gap-1.5">
            <svg class="w-3.5 h-3.5 text-[#3b82f6]" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"/></svg>
            Suhbatlar va Audio Yozuvlar (${Number(data.calls.length)})
          </span>
          <span class="text-[10px] text-[#64748b]">MoiZvonki + Whisper STT</span>
        </div>
        <div class="flex flex-col gap-2.5">
          ${data.calls.map((c, i) => buildAudioPlayerHtml(c, `call_audio_${safeLeadId}_${i}`)).join("")}
        </div>
      `;
    } else {
      container.innerHTML = `
        <div class="text-[11px] text-[#94a3b8] italic text-center py-2">
          Ushbu bitim boʻyicha audio yozuvlar hali mavjud emas
        </div>
      `;
    }
  } catch (e) {
    console.error("Load call history error:", e);
  }
}

function _safeAudioUrl(raw) {
  const s = String(raw || "").trim();
  if (!s) return "";
  try {
    const parsed = new URL(s, window.location.origin);
    if (parsed.protocol === "https:" || parsed.protocol === "http:") {
      return _escCall(`${parsed.origin}${parsed.pathname}${parsed.search}`);
    }
  } catch (_) {
    return "";
  }
  return "";
}

function buildAudioPlayerHtml(call, uniqueId) {
  const isIncoming = call.direction === "in" || call.direction === "incoming";
  const dirBadge = isIncoming
    ? '<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-[#dcfce7] text-[#15803d]">↙ Kiruvchi</span>'
    : '<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-[#dbeafe] text-[#1d4ed8]">↗ Chiquvchi</span>';

  const safeId = String(uniqueId || "").replace(/[^A-Za-z0-9_-]/g, "");
  const audioUrl = _safeAudioUrl(call.audio_url);
  const durStr = _escCall(call.duration_formatted || `${Number.parseInt(call.duration || 0, 10) || 0}s`);
  const safeLeadId = Number.parseInt(call.lead_id || (window.activeDrawerLead ? window.activeDrawerLead.id : 0), 10) || 0;

  const transcript = call.transcript || "";
  const ai = call.ai_analysis || {};
  const bantScore = Math.max(0, Math.min(100, Number.parseInt(ai.bant_score || 0, 10) || 0));

  return `
    <div class="p-2.5 rounded-lg border border-[#e2e8f0] bg-[#f8fafc] flex flex-col gap-2 text-xs shadow-2xs">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-1.5">
          ${dirBadge}
          <span class="font-bold text-[#1e293b]">${_escCall(call.by || "Sotuvchi")}</span>
        </div>
        <span class="text-[10px] text-[#64748b]">${_escCall(call.time || "Bugun")}</span>
      </div>

      ${audioUrl ? `
        <div class="flex items-center gap-2 bg-white p-2 rounded border border-[#cbd5e1]">
          <button type="button" data-audio-url="${audioUrl}" onclick="togglePlayAudio('${safeId}', this.dataset.audioUrl)" id="btn_${safeId}" class="w-8 h-8 rounded-full bg-[#3b82f6] text-white flex items-center justify-center hover:bg-[#2563eb] transition shrink-0 shadow-xs" title="Ijro etish / Toʻxtatish">
            <svg id="icon_play_${safeId}" class="w-4 h-4 ml-0.5" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
            <svg id="icon_pause_${safeId}" class="w-4 h-4 hidden" fill="currentColor" viewBox="0 0 24 24"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>
          </button>

          <div class="flex flex-col flex-1 min-w-0">
            <input type="range" id="seek_${safeId}" min="0" max="100" value="0" oninput="seekAudio('${safeId}')" class="w-full h-1 bg-[#e2e8f0] rounded-lg appearance-none cursor-pointer accent-[#3b82f6]">
            <div class="flex items-center justify-between text-[10px] text-[#64748b] mt-1 font-mono">
              <span id="time_${safeId}">0:00</span>
              <span>${durStr}</span>
            </div>
          </div>

          <div class="flex items-center gap-1 shrink-0">
            <button type="button" onclick="cycleAudioSpeed('${safeId}')" id="speed_${safeId}" class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-[#f1f5f9] text-[#475569] hover:bg-[#e2e8f0]" title="Tezlik">1.0x</button>
            <a href="${audioUrl}" target="_blank" rel="noopener noreferrer" download class="p-1 text-[#64748b] hover:text-[#1e293b]" title="Yuklab olish">
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>
            </a>
          </div>
          <audio id="audio_${safeId}" preload="metadata" src="${audioUrl}" ontimeupdate="updateAudioProgress('${safeId}')" onended="onAudioEnded('${safeId}')"></audio>
        </div>
      ` : `
        <div class="text-[11px] text-[#94a3b8] italic">Audio yozuv mavjud emas (MoiZvonki telefonda saqlangan)</div>
      `}

      <!-- WHISPER STT VA AI TAHLIL BLOKI -->
      ${transcript ? `
        <div class="mt-1 pt-2 border-t border-[#e2e8f0] flex flex-col gap-1.5">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-1.5">
              ${bantScore > 0 ? `<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-[#eff6ff] text-[#1d4ed8]">BANT: ${bantScore}/100</span>` : ''}
              ${ai.sentiment ? `<span class="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-[#ecfdf5] text-[#047857]">${_escCall(ai.sentiment)}</span>` : ''}
            </div>
            <button type="button" onclick="toggleTranscriptBox('${safeId}')" class="text-[11px] font-bold text-[#0284c7] hover:underline flex items-center gap-0.5">
              <span id="txt_toggle_${safeId}">Transkripsiya matni ▼</span>
            </button>
          </div>
          ${ai.summary ? `<div class="text-[12px] text-[#334155] leading-relaxed"><b>Xulosa:</b> ${_escCall(ai.summary)}</div>` : ''}
          ${ai.pain_point ? `<div class="text-[11px] text-[#b45309] bg-[#fffbeb] p-1.5 rounded border border-[#fde68a]"><b>Mijoz ogʻrigʻi:</b> ${_escCall(ai.pain_point)}</div>` : ''}
          <div id="transcript_box_${safeId}" class="hidden mt-1 p-2 bg-white rounded border border-[#e2e8f0] font-mono text-[11px] text-[#1e293b] leading-relaxed max-h-40 overflow-y-auto whitespace-pre-line custom-scrollbar">
            ${_escCall(transcript)}
          </div>
        </div>
      ` : audioUrl ? `
        <div class="mt-1 pt-1.5 border-t border-[#e2e8f0] flex items-center justify-between">
          <span class="text-[10px] text-[#94a3b8] italic">Transkripsiya olinmagan</span>
          <button type="button" id="btn_stt_${safeId}" data-audio-url="${audioUrl}" onclick="requestCallTranscription(${safeLeadId}, this.dataset.audioUrl, '${safeId}')" class="px-2 py-1 rounded text-[11px] font-bold bg-[#f0f9ff] text-[#0284c7] hover:bg-[#e0f2fe] border border-[#bae6fd] flex items-center gap-1 transition shadow-2xs">
            ✨ AI Transkripsiya & BANT
          </button>
        </div>
      ` : ''}
    </div>
  `;
}

async function requestCallTranscription(leadId, audioUrl, uniqueId) {
  const btn = document.getElementById(`btn_stt_${uniqueId}`);
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span>⏳ Transkripsiya qilinmoqda...</span>`;
  }

  try {
    const token = getCrmAuthToken();
    const headers = { "Content-Type": "application/json" };
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
      headers["X-CRM-Session-Token"] = token;
    }

    const res = await fetch("/api/crm/dialer/calls/transcribe", {
      method: "POST",
      headers: headers,
      body: JSON.stringify({ lead_id: parseInt(leadId, 10), audio_url: audioUrl }),
    });

    const data = await res.json();
    if (res.ok && data.success) {
      if (typeof showToast === "function") showToast("Qo'ng'iroq transkripsiya qilindi!");
      if (typeof loadLeadCallHistory === "function") loadLeadCallHistory(leadId);
      if (window.activeDrawerLead && data.analysis) {
        window.activeDrawerLead.ai_analysis = data.analysis;
        if (typeof renderDrawerAiAnalysis === "function") renderDrawerAiAnalysis(data.analysis);
      }
    } else {
      if (typeof showToast === "function") showToast(data.detail || "Transkripsiya xatosi yuz berdi");
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = "Qayta urinish";
      }
    }
  } catch (e) {
    console.error("Transcribe request error:", e);
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = "Xatolik";
    }
  }
}

function toggleTranscriptBox(uniqueId) {
  const box = document.getElementById(`transcript_box_${uniqueId}`);
  const label = document.getElementById(`txt_toggle_${uniqueId}`);
  if (!box) return;
  const isHidden = box.classList.toggle("hidden");
  if (label) label.innerText = isHidden ? "Transkripsiya matni ▼" : "Yashirish ▲";
}

function togglePlayAudio(uniqueId, url) {
  const audioEl = document.getElementById(`audio_${uniqueId}`);
  const iconPlay = document.getElementById(`icon_play_${uniqueId}`);
  const iconPause = document.getElementById(`icon_pause_${uniqueId}`);
  if (!audioEl) return;

  if (currentPlayingAudio && currentPlayingAudio !== audioEl) {
    currentPlayingAudio.pause();
    document.querySelectorAll('[id^="icon_pause_"]').forEach((el) => el.classList.add("hidden"));
    document.querySelectorAll('[id^="icon_play_"]').forEach((el) => el.classList.remove("hidden"));
  }

  if (audioEl.paused) {
    audioEl.play().then(() => {
      currentPlayingAudio = audioEl;
      if (iconPlay) iconPlay.classList.add("hidden");
      if (iconPause) iconPause.classList.remove("hidden");
    }).catch((e) => {
      console.warn("Audio play failed, trying proxy...", e);
      const proxyUrl = `/api/crm/dialer/calls/proxy-audio?url=${encodeURIComponent(url)}`;
      audioEl.src = proxyUrl;
      audioEl.play();
    });
  } else {
    audioEl.pause();
    if (iconPlay) iconPlay.classList.remove("hidden");
    if (iconPause) iconPause.classList.add("hidden");
  }
}

function updateAudioProgress(uniqueId) {
  const audioEl = document.getElementById(`audio_${uniqueId}`);
  const seek = document.getElementById(`seek_${uniqueId}`);
  const timeEl = document.getElementById(`time_${uniqueId}`);
  if (!audioEl || !seek || !timeEl) return;

  if (audioEl.duration) {
    const pct = (audioEl.currentTime / audioEl.duration) * 100;
    seek.value = pct;
    const curMin = Math.floor(audioEl.currentTime / 60);
    const curSec = Math.floor(audioEl.currentTime % 60);
    timeEl.innerText = `${curMin}:${curSec < 10 ? "0" : ""}${curSec}`;
  }
}

function seekAudio(uniqueId) {
  const audioEl = document.getElementById(`audio_${uniqueId}`);
  const seek = document.getElementById(`seek_${uniqueId}`);
  if (!audioEl || !seek || !audioEl.duration) return;
  audioEl.currentTime = (seek.value / 100) * audioEl.duration;
}

function cycleAudioSpeed(uniqueId) {
  const audioEl = document.getElementById(`audio_${uniqueId}`);
  const speedBtn = document.getElementById(`speed_${uniqueId}`);
  if (!audioEl || !speedBtn) return;

  const speeds = [1.0, 1.25, 1.5, 2.0];
  const curSpeed = audioEl.playbackRate || 1.0;
  const nextIdx = (speeds.indexOf(curSpeed) + 1) % speeds.length;
  const newSpeed = speeds[nextIdx];
  audioEl.playbackRate = newSpeed;
  speedBtn.innerText = `${newSpeed.toFixed(1)}x`;
}

function onAudioEnded(uniqueId) {
  const iconPlay = document.getElementById(`icon_play_${uniqueId}`);
  const iconPause = document.getElementById(`icon_pause_${uniqueId}`);
  const seek = document.getElementById(`seek_${uniqueId}`);
  if (iconPlay) iconPlay.classList.remove("hidden");
  if (iconPause) iconPause.classList.add("hidden");
  if (seek) seek.value = 0;
  currentPlayingAudio = null;
}

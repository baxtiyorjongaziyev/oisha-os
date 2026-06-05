"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

interface TranscriptLine {
  speaker: "Mijoz" | "Menejer";
  time: string;
  text: string;
}

export default function CallDetailsPage() {
  const params = useParams();
  const router = useRouter();
  const callId = params.id as string;

  // Interactive audio states
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(1);
  const [currentTime, setCurrentTime] = useState("0:00");
  const [transcriptExpanded, setTranscriptExpanded] = useState(false);
  const [shareLinkCopied, setShareLinkCopied] = useState(false);

  const mockTranscript: TranscriptLine[] = [
    { speaker: "Menejer", time: "0:01", text: "Assalomu alaykum! Jon Branding agentligi, Baxtiyorjonman. Eshityapman?" },
    { speaker: "Mijoz", time: "0:04", text: "Vaalaykum assalom. Ha, eshityapman. Yangi brend uchun nomlash (naming) bo'yicha so'rov qoldirgandim." },
    { speaker: "Menejer", time: "0:10", text: "Ha, juda yaxshi. Biz aynan shu yo'nalish bo'yicha ko'plab loyihalar qilganmiz. Naming bo'yicha qanday talablaringiz bor?" },
    { speaker: "Mijoz", time: "0:15", text: "Bizga o'zbekona, lekin xalqaro bozorga ham mos keladigan qisqa va esda qolarli nom kerak." },
    { speaker: "Menejer", time: "0:21", text: "Tushunarli. Biznesingiz qaysi sohada, shuni ayta olasizmi?" },
    { speaker: "Mijoz", time: "0:24", text: "Oziq-ovqat mahsulotlari ishlab chiqarish, asosan quruq mevalar va yong'oqlar qadoqlash." },
    { speaker: "Menejer", time: "0:29", text: "Ajoyib. Biz loyiha brifini to'ldirishimiz kerak. Men sizga telegramdan brif yuboraman, shuni to'ldirib bersangiz batafsil tahlil qilamiz." },
    { speaker: "Mijoz", time: "0:35", text: "Bo'pti, yuboring. Keyin narxlari va patentlash masalalarini ham gaplashamiz." },
    { speaker: "Menejer", time: "0:39", text: "Albatta, xullas patentlash bo'yicha ham to'liq tekshirib beramiz. Brifni kutaman." },
    // Hidden lines
    { speaker: "Mijoz", time: "0:43", text: "Rahmat, kutaman telegramda." },
    { speaker: "Menejer", time: "0:46", text: "Sog' bo'ling, salomat bo'ling." }
  ];

  const visibleTranscript = transcriptExpanded 
    ? mockTranscript 
    : mockTranscript.slice(0, 9);

  const handleShare = () => {
    setShareLinkCopied(true);
    navigator.clipboard.writeText(window.location.href);
    setTimeout(() => setShareLinkCopied(false), 3000);
  };

  return (
    <div className="space-y-6">
      {/* Top Navigation */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <button
          onClick={() => router.back()}
          className="flex items-center gap-2 text-xs font-semibold text-text-muted hover:text-brand"
        >
          ← Orqaga
        </button>

        <div className="flex items-center gap-2">
          <span className="rounded-full bg-emerald-100 px-3 py-0.5 text-xs font-bold text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-400">
            Bog&apos;langan
          </span>
          <span className="text-xs text-text-muted">2026-06-03 14:22</span>
          
          <Link
            href="/crm/leads/lead-1"
            className="rounded-xl border border-border bg-bg-card hover:bg-bg text-text text-xs font-semibold px-3.5 py-1.5 transition-colors inline-block"
          >
            Lid tafsilotlari ↗
          </Link>

          <button
            onClick={handleShare}
            className="rounded-xl bg-brand text-white text-xs font-semibold px-3.5 py-1.5 hover:bg-brand-hover shadow-md transition-colors"
          >
            {shareLinkCopied ? "Havola nusxalandi!" : "Ulashish 🔗"}
          </button>
        </div>
      </div>

      {/* Main summary block */}
      <div className="rounded-3xl border border-border bg-bg-card p-6 shadow-sm space-y-4">
        <div>
          <h3 className="text-base font-bold text-text">Suhbatda nima bo&apos;ldi va bu nimani anglatadi?</h3>
          <p className="text-xs text-text-muted mt-2 leading-relaxed">
            Mijoz quruq mevalar ishlab chiqarish biznesi uchun yangi brend nomi (naming) bo&apos;yicha murojaat qilgan. Suhbat davomida brend xalqaro talablarga javob berishi va o&apos;zbekcha ildizga ega bo&apos;lishi kerakligi aytildi. Menejer mijozga brif yuborishga va keyinchalik patentlash masalalarini ham kelishishga va&apos;da berdi.
          </p>
        </div>
        
        {/* Badges/Tags */}
        <div className="flex flex-wrap gap-2 pt-2 border-t border-border/50">
          <span className="rounded-lg bg-brand-light px-2.5 py-1 text-[10px] font-bold text-brand uppercase">
            Qo&apos;ng&apos;iroq oilasi: Lidni aniqlash
          </span>
          <span className="rounded-lg bg-brand-light px-2.5 py-1 text-[10px] font-bold text-brand uppercase">
            Biznesga tegishli
          </span>
          <span className="rounded-lg bg-brand-light px-2.5 py-1 text-[10px] font-bold text-brand uppercase">
            Xizmat: Naming (Nomlash)
          </span>
          <Link
            href="/crm/leads/lead-1"
            className="flex items-center gap-1 rounded-lg bg-bg px-2.5 py-1 text-[10px] font-semibold text-text-muted hover:text-brand border border-border"
          >
            AmoCRM sdelka ↗
          </Link>
        </div>
      </div>

      {/* Grid: 3 KPI Cards */}
      <div className="grid md:grid-cols-3 gap-6">
        {/* Card 1 */}
        <div className="rounded-3xl border border-border bg-bg-card p-5 shadow-sm space-y-2">
          <h4 className="text-xs font-bold text-text-muted uppercase">1. Bu qo&apos;ng&apos;iroq sotuvni oldinga surdimi?</h4>
          <p className="text-xs text-text font-semibold">Siljish bor, ammo keyingi aloqa mustahkam emas.</p>
          <div className="text-[10px] text-text-muted mt-1">
            Menejer brif yuborishga kelishib oldi, ammo aniq topshiriq topshirish vaqti yoki qayta qo&apos;ng&apos;iroq sanasini qat&apos;iy belgilamadi.
          </div>
        </div>

        {/* Card 2 */}
        <div className="rounded-3xl border border-border bg-bg-card p-5 shadow-sm space-y-2">
          <h4 className="text-xs font-bold text-text-muted uppercase">2. Endi keyingi qadam nima?</h4>
          <p className="text-xs text-brand font-bold">Brifni to&apos;ldirish va fikr olish.</p>
          <div className="text-[10px] text-text-muted mt-1">
            Mijozga dushanba kuni soat 10:00 da Telegram orqali bog&apos;lanib, yuborilgan naming brifining to&apos;ldirilgan holatini so&apos;rash va uchrashuv belgilash.
          </div>
        </div>

        {/* Card 3 */}
        <div className="rounded-3xl border border-border bg-bg-card p-5 shadow-sm space-y-2">
          <h4 className="text-xs font-bold text-text-muted uppercase">3. Qo&apos;ng&apos;iroq konteksti</h4>
          <div className="space-y-1 mt-2 text-[10px]">
            <div className="flex justify-between"><span className="text-text-muted">ID:</span> <span className="font-semibold text-text">call-{callId}</span></div>
            <div className="flex justify-between"><span className="text-text-muted">Davomiylik:</span> <span className="font-semibold text-text">0:39 daqiqa</span></div>
            <div className="flex justify-between"><span className="text-text-muted">Yo&apos;nalish:</span> <span className="font-semibold text-text">Kiruvchi</span></div>
            <div className="flex justify-between"><span className="text-text-muted">Menejer:</span> <span className="font-semibold text-text">Baxtiyorjon Gaziyev</span></div>
          </div>
        </div>
      </div>

      {/* Speech Balance & Customer profile grid */}
      <div className="grid md:grid-cols-2 gap-6">
        {/* Speech Dynamics */}
        <div className="rounded-3xl border border-border bg-bg-card p-6 shadow-sm space-y-4">
          <h3 className="text-sm font-bold text-text">Suhbat dinamikasi</h3>
          <div className="flex justify-between text-xs font-semibold text-text-muted">
            <span>Menejer: 49%</span>
            <span>Mijoz: 51%</span>
          </div>
          <div className="flex h-4 w-full rounded-full overflow-hidden bg-bg">
            <div className="bg-brand h-full transition-all" style={{ width: "49%" }}></div>
            <div className="bg-emerald-500 h-full transition-all" style={{ width: "51%" }}></div>
          </div>
          <div className="flex items-center gap-4 text-[10px] text-text-muted">
            <div className="flex items-center gap-1">
              <span className="h-2.5 w-2.5 rounded bg-brand inline-block"></span> Menejer
            </div>
            <div className="flex items-center gap-1">
              <span className="h-2.5 w-2.5 rounded bg-emerald-500 inline-block"></span> Mijoz
            </div>
          </div>
        </div>

        {/* Customer Profile */}
        <div className="rounded-3xl border border-border bg-bg-card p-6 shadow-sm space-y-3">
          <h3 className="text-sm font-bold text-text">Mijoz ma&apos;lumotlari</h3>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between border-b border-border/40 pb-1">
              <span className="text-text-muted">Ismi:</span>
              <span className="font-bold text-text">Hasanboy Gaziyev</span>
            </div>
            <div className="flex justify-between border-b border-border/40 pb-1">
              <span className="text-text-muted">Kompaniya:</span>
              <span className="font-bold text-text">Avtokontakt MCHJ</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">Qaror qabul qiluvchi:</span>
              <span className="rounded bg-emerald-100 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-400 px-2 py-0.5 text-[10px] font-bold">
                Ha
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Interactive Audio Player widget */}
      <div className="rounded-3xl border border-border bg-bg-card p-5 shadow-sm space-y-4">
        <h3 className="text-sm font-bold text-text">Qo&apos;ng&apos;iroq audiosi</h3>
        <div className="flex flex-col md:flex-row items-center gap-4">
          {/* Play/Pause Button */}
          <button
            onClick={() => {
              setIsPlaying(!isPlaying);
              if (!isPlaying) {
                // mock play progress
                setCurrentTime("0:12");
              } else {
                setCurrentTime("0:00");
              }
            }}
            className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-brand text-white hover:bg-brand-hover shadow-lg shadow-brand/15 transition-transform active:scale-95 focus:outline-none"
          >
            {isPlaying ? (
              <span className="text-xs font-bold font-mono">||</span>
            ) : (
              <span className="text-xs pl-0.5">▶</span>
            )}
          </button>

          {/* Progress timeline */}
          <div className="flex-1 w-full space-y-1">
            <div className="flex justify-between text-[10px] text-text-muted font-mono">
              <span>{currentTime}</span>
              <span>0:39</span>
            </div>
            <div className="h-2 w-full rounded-full bg-bg relative overflow-hidden cursor-pointer">
              <div 
                className="absolute top-0 bottom-0 left-0 bg-brand rounded-full transition-all duration-300"
                style={{ width: isPlaying ? "30%" : "0%" }}
              ></div>
            </div>
          </div>

          {/* Playback speed selector */}
          <div className="flex rounded-xl bg-bg border border-border p-1">
            {[1, 1.25, 1.5, 2].map((speed) => (
              <button
                key={speed}
                onClick={() => setPlaybackSpeed(speed)}
                className={`rounded-lg px-2.5 py-1 text-[10px] font-bold transition-all ${
                  playbackSpeed === speed ? "bg-brand text-white" : "text-text-muted hover:text-brand"
                }`}
              >
                {speed}x
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Audio transcript bubbles */}
      <div className="rounded-3xl border border-border bg-bg-card p-6 shadow-sm space-y-4">
        <h3 className="text-sm font-bold text-text">Muloqot matni (Transkript)</h3>
        
        <div className="space-y-3.5 max-h-[400px] overflow-y-auto pr-2">
          {visibleTranscript.map((line, i) => (
            <div
              key={i}
              className={`flex gap-3 max-w-[85%] ${
                line.speaker === "Menejer" ? "ml-auto flex-row-reverse text-right" : "mr-auto"
              }`}
            >
              {/* Speaker initial tag */}
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-xl bg-bg text-[10px] font-bold text-text-muted border border-border uppercase">
                {line.speaker[0]}
              </div>

              {/* Chat bubble */}
              <div
                className={`rounded-2xl p-3 text-xs leading-relaxed transition-all cursor-pointer hover:opacity-90 ${
                  line.speaker === "Menejer"
                    ? "bg-brand-light text-brand"
                    : "bg-bg text-text"
                }`}
                onClick={() => {
                  setCurrentTime(line.time);
                  setIsPlaying(true);
                }}
              >
                <div className="flex items-center gap-2 justify-between mb-1">
                  <span className="font-bold text-[9px] uppercase tracking-wider">{line.speaker}</span>
                  <span className="font-mono text-[9px] text-text-muted">{line.time}</span>
                </div>
                <div>{line.text}</div>
              </div>
            </div>
          ))}
        </div>

        {/* View more buttons */}
        <div className="text-center pt-2 border-t border-border/40">
          <button
            onClick={() => setTranscriptExpanded(!transcriptExpanded)}
            className="text-xs font-bold text-brand hover:underline"
          >
            {transcriptExpanded ? "Yig'ish ▴" : "Yana 2 qatorni ko'rsatish ▾"}
          </button>
        </div>
      </div>

      {/* Voice Scoring/Analysis parameters */}
      <div className="grid md:grid-cols-2 gap-6">
        {/* Voice analysis cards */}
        <div className="rounded-3xl border border-border bg-bg-card p-6 shadow-sm space-y-4">
          <h3 className="text-sm font-bold text-text">Ovoz tahlili</h3>
          
          <div className="space-y-4">
            {/* Dictation */}
            <div className="space-y-1">
              <div className="flex justify-between text-xs">
                <span className="font-semibold text-text-muted">Diksiya</span>
                <span className="font-bold text-emerald-600">90%</span>
              </div>
              <div className="h-2 w-full rounded-full bg-bg overflow-hidden">
                <div className="h-full bg-emerald-500 rounded-full" style={{ width: "90%" }}></div>
              </div>
            </div>

            {/* Metrics cards */}
            <div className="grid grid-cols-3 gap-2">
              <div className="rounded-xl border border-border p-2.5 text-center">
                <div className="text-[9px] font-bold text-text-muted uppercase">Ohang</div>
                <div className="text-xs font-bold text-brand mt-1">Do&apos;stona</div>
              </div>
              <div className="rounded-xl border border-border p-2.5 text-center">
                <div className="text-[9px] font-bold text-text-muted uppercase">Tezlik</div>
                <div className="text-xs font-bold text-brand mt-1">80 so&apos;z</div>
              </div>
              <div className="rounded-xl border border-border p-2.5 text-center">
                <div className="text-[9px] font-bold text-text-muted uppercase">Energiya</div>
                <div className="text-xs font-bold text-brand mt-1">O&apos;rtacha</div>
              </div>
            </div>

            {/* Filler words tags */}
            <div className="space-y-1.5">
              <div className="text-[10px] font-bold text-text-muted uppercase">Ortiqcha to&apos;ldiruvchi so&apos;zlar:</div>
              <div className="flex flex-wrap gap-1.5">
                <span className="rounded bg-rose-50 dark:bg-rose-950/20 text-rose-600 dark:text-rose-400 border border-rose-100 dark:border-rose-900/30 text-[10px] font-bold px-2 py-0.5">
                  &quot;xullas&quot; (1 ta)
                </span>
                <span className="rounded bg-rose-50 dark:bg-rose-950/20 text-rose-600 dark:text-rose-400 border border-rose-100 dark:border-rose-900/30 text-[10px] font-bold px-2 py-0.5">
                  &quot;xo&apos;sh&quot; (1 ta)
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Signals, agreements and objections */}
        <div className="rounded-3xl border border-border bg-bg-card p-6 shadow-sm space-y-4">
          <h3 className="text-sm font-bold text-text">Signallar va Kelishuvlar</h3>
          
          <div className="space-y-3.5 text-xs">
            {/* Urgency */}
            <div>
              <div className="text-[10px] font-bold text-text-muted uppercase mb-1">Operatsion signallar</div>
              <div className="flex flex-wrap gap-1.5">
                <span className="rounded bg-brand-light text-brand px-2.5 py-1 font-bold">
                  Shoshilinchlik: Hozir
                </span>
                <span className="rounded bg-bg text-text-muted border border-border px-2.5 py-1 font-semibold">
                  Byudjet: Muhokama qilinmadi
                </span>
              </div>
            </div>

            {/* Agreements */}
            <div>
              <div className="text-[10px] font-bold text-text-muted uppercase mb-1">Kelishuvlar</div>
              <div className="space-y-1.5">
                <div className="flex items-center gap-2 rounded-xl bg-bg p-2 border border-border">
                  <span className="rounded bg-brand text-white text-[9px] font-bold px-1.5 py-0.5 uppercase">Menejer</span>
                  <span className="text-[11px] text-text">Telegram orqali loyiha brifini yuborishi kerak.</span>
                </div>
                <div className="flex items-center gap-2 rounded-xl bg-bg p-2 border border-border">
                  <span className="rounded bg-emerald-500 text-white text-[9px] font-bold px-1.5 py-0.5 uppercase">Mijoz</span>
                  <span className="text-[11px] text-text">Yuborilgan brifni to&apos;ldirib, qaytarishi kerak.</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

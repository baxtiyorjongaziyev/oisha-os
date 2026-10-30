"use client";

import React from "react";
import { useParams, useRouter } from "next/navigation";

// Bitim tafsilotlari hali hech qaysi manbaga ulanmagan. Oldin bu yerda qo'lda
// yozilgan namuna ma'lumot turardi; real ish oddiy CRM sahifasida.
export default function CRMLeadPage() {
  const params = useParams();
  const router = useRouter();
  const leadId = params.id as string;

  return (
    <div className="space-y-6">
      <div>
        <button
          onClick={() => router.back()}
          className="flex items-center gap-2 text-xs font-semibold text-text-muted hover:text-brand"
        >
          &larr; Orqaga
        </button>
      </div>

      <div className="rounded-3xl border border-border bg-bg-card p-6 shadow-sm space-y-4">
        <div>
          <span className="text-[10px] font-bold text-text-muted uppercase tracking-wider">Bitim #{leadId}</span>
          <h1 className="text-lg font-bold text-text mt-1">Bitim tafsilotlari bu sahifada hali ko&apos;rsatilmaydi</h1>
          <p className="text-sm text-text-muted mt-1">
            Mijozni ko&apos;rish, qo&apos;ng&apos;iroq yozish va bosqichni o&apos;zgartirish uchun oddiy CRM sahifasini oching.
          </p>
        </div>
        <a
          href="/api/simple-crm/"
          className="inline-block rounded-xl bg-brand text-white px-6 py-3 text-base font-bold hover:bg-brand-hover"
        >
          CRM&apos;ni ochish
        </a>
      </div>
    </div>
  );
}

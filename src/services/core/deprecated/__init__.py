"""
Deprecated — production kodida HECH QACHON import qilinmasin.

Bu fayllar 2026-06 arxitektura tozalashida aniqlandiki, ular hech qaysi
production yo'lida import qilinmaydi. Tarixiy ma'lumot uchun saqlanadi.

Fayllar:
  singularity_core     — EscalationAgent wrapperi (hech yerda chaqirilmagan)
  sales_rep_service    — SalesAgent ustidagi keraksiz qatlam
  sales_rep_handlers   — sales_rep_service uchun handlerlar
  sales_coach_context  — sales_coach.py bilan parallel, ulanmagan
  onboarding_manager   — AdvisorAgent wrapperi (hech yerda import yo'q)
  unanswered_monitor   — AutoLeadAgent wrapperi (hech yerda import yo'q)
  boot_catchup         — Faqat commentda eslatilgan
  channel_forwarder    — 0 ref
  conversion_checker   — 0 ref
"""

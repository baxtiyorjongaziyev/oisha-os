"""
Deprecated modules. Do not import in production.

Deprecated â€” production kodida HECH QACHON import qilinmasin.

Bu fayllar 2026-06 arxitektura tozalashida aniqlandiki, ular hech qaysi
production yo'lida import qilinmaydi. Tarixiy ma'lumot uchun saqlanadi.

Fayllar:
  singularity_core     â€” EscalationAgent wrapperi (hech yerda chaqirilmagan)
  sales_rep_service    â€” SalesAgent ustidagi keraksiz qatlam
  sales_rep_handlers   â€” sales_rep_service uchun handlerlar
  sales_coach_context  â€” sales_coach.py bilan parallel, ulanmagan
  onboarding_manager   â€” AdvisorAgent wrapperi (hech yerda import yo'q)
  unanswered_monitor   â€” AutoLeadAgent wrapperi (hech yerda import yo'q)
  boot_catchup         â€” Faqat commentda eslatilgan
  channel_forwarder    â€” 0 ref
  conversion_checker   â€” 0 ref
"""

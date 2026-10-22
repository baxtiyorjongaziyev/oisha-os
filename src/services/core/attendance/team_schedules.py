"""Jamoaning shaxsiy ish grafiklari.

Manba: owner (Baxtiyorjon) aytgan, 2026-10-22. Hafta kunlari ISO: 1=Du ... 7=Ya.
Ish vaqti hamma uchun 10:00–19:00. Bazaga ``scripts/attendance_seed_schedules.py`` yozadi.
"""

DEFAULT_WEEKDAYS = [1, 2, 3, 4, 5, 6]

TEAM_SCHEDULES = [
    {"name": "Mumtozmaxal", "weekdays": [1, 2, 4, 5, 6, 7], "note": "Dam olish kunini chorshanbaga ko'chirgan"},
    {"name": "Ahror", "weekdays": [1, 2, 3, 4, 5, 6, 7], "note": "7 kun ishlaydi"},
    {"name": "Hasanboy", "weekdays": [1, 2, 3, 4, 5, 6], "optional_weekdays": [7], "note": "Yakshanba ixtiyoriy"},
    {"name": "Baxtiyorjon", "weekdays": DEFAULT_WEEKDAYS, "note": "Yakshanba dam"},
    {"name": "Rayxona", "weekdays": DEFAULT_WEEKDAYS, "note": "Yakshanba dam"},
    {"name": "Shahnoza", "weekdays": DEFAULT_WEEKDAYS, "note": "Yakshanba dam"},
]

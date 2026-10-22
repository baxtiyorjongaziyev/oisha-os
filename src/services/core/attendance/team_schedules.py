"""Jamoaning shaxsiy ish grafiklari.

Manba: owner (Baxtiyorjon) aytgan, 2026-10-22. Hafta kunlari ISO: 1=Du ... 7=Ya.
Ish vaqti hamma uchun 10:00–19:00. Bazaga ``scripts/attendance_seed_schedules.py`` yozadi.
"""

DEFAULT_WEEKDAYS = [1, 2, 3, 4, 5, 6]

# Owner yuborgan (2026-10-22): U-Enter Innovatsion Center, Toshkent — plus code 874J+7H8.
# Radius bino o'lchami va ichkaridagi GPS xatosi uchun 150 m; aniqlik chegarasi 75 m.
OFFICE = {"name": "U-Enter Innovatsion Center", "latitude": 41.3056580, "longitude": 69.2814659,
          "radius_m": 150, "max_accuracy_m": 75}

TEAM_SCHEDULES = [
    {"name": "Mumtozmaxal", "weekdays": [1, 2, 4, 5, 6, 7], "note": "Dam olish kunini chorshanbaga ko'chirgan"},
    {"name": "Ahror", "weekdays": [1, 2, 3, 4, 5, 6, 7], "note": "7 kun ishlaydi"},
    {"name": "Hasanboy", "weekdays": [1, 2, 3, 4, 5, 6], "optional_weekdays": [7], "note": "Yakshanba ixtiyoriy"},
    {"name": "Baxtiyorjon", "weekdays": DEFAULT_WEEKDAYS, "note": "Yakshanba dam"},
    {"name": "Rayxona", "weekdays": DEFAULT_WEEKDAYS, "note": "Yakshanba dam"},
    {"name": "Shahnoza", "weekdays": DEFAULT_WEEKDAYS, "note": "Yakshanba dam"},
]

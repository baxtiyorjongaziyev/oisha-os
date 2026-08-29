"""
AI Agent Tools — Gemini Function Calling uchun barcha toollar.

Bu modul botni chatbot darajasidan AI Agent darajasiga ko'taradi.
Gemini o'zi qaysi tool ni qachon ishlatishini hal qiladi va chaqiradi.
"""

import logging
import datetime
import asyncio
import inspect
from typing import Any, Optional, Dict

logger = logging.getLogger(__name__)

# ==================== GEMINI FUNCTION DECLARATIONS ====================
# Bu ro'yxat Gemini modeliga "sen bu amallarni bajara olasan" deb ko'rsatiladi

TOOL_DECLARATIONS = [
    {
        "name": "save_lead_info",
        "description": (
            "Mijoz haqidagi ma'lumotni CRM bazaga saqlash. "
            "Agar mijoz ism, telefon raqam, biznes turi, hudud yoki boshqa kontakt "
            "ma'lumotlarini berib qo'ysa, BU TOOLNI CHAQIRING. "
            "Barcha ma'lumotlar ixtiyoriy — faqat mavjud bo'lganlarini yuboring."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "Telegram foydalanuvchi ID si",
                },
                "name": {
                    "type": "string",
                    "description": "Mijoz ismi (Telegram ismi yoki o'zi aytgan ism)",
                },
                "phone": {
                    "type": "string",
                    "description": "Telefon raqam (+998XXXXXXXXX formatida)",
                },
                "business_type": {
                    "type": "string",
                    "description": "Biznes turi (restoran, salon, do'kon va h.k.)",
                },
                "region": {
                    "type": "string",
                    "description": "Hudud yoki shahar (Toshkent, Samarqand va h.k.)",
                },
                "brand_name": {
                    "type": "string",
                    "description": "Brend yoki kompaniya nomi",
                },
                "service_type": {
                    "type": "string",
                    "description": "Kerakli xizmat (logo, naming, branding strategiya va h.k.)",
                },
                "deadline": {
                    "type": "string",
                    "description": "Muddat yoki sana (masalan: '2 hafta', '1 mart')",
                },
                "lead_quality": {
                    "type": "string",
                    "description": "Lead sifati: 'Sifatli', 'Oddiy', yoki 'Unknown'",
                    "enum": ["Sifatli", "Oddiy", "Unknown", "Sifatsiz"],
                },
            },
            "required": ["user_id"],
        },
    },
    {
        "name": "create_calendar_event",
        "description": (
            "Google Calendar da uchrashuv yoki tadbir yaratish. "
            "Mijoz aniq sana va vaqt bilan uchrashuvni tasdiqlasa yoki "
            "'ertaga soat 14da' kabi vaqt belgilab qo'ysa, BU TOOLNI CHAQIRING."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "Uchrashuv mavzusi yoki nomi",
                },
                "start_time": {
                    "type": "string",
                    "description": "Boshlanish vaqti ISO 8601 formatida (masalan: '2026-03-13T14:00:00')",
                },
                "end_time": {
                    "type": "string",
                    "description": "Tugash vaqti ISO 8601 formatida. Ko'rsatilmasa, 1 soat qo'shiladi.",
                },
                "description": {
                    "type": "string",
                    "description": "Uchrashuv tavsifi yoki qo'shimcha ma'lumot",
                },
            },
            "required": ["summary", "start_time"],
        },
    },
    {
        "name": "save_google_contact",
        "description": (
            "Mijozni Google Contacts ga saqlash. "
            "Telefon raqami va ism mavjud bo'lsa, bu toolni chaqiring. "
            "save_lead_info dan farqi: bu Google Contacts da saqlaydi (sinxronizatsiya uchun)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Mijoz ismi"},
                "phone": {"type": "string", "description": "Telefon raqam"},
                "note": {
                    "type": "string",
                    "description": "Qo'shimcha izoh (masalan: kerakli xizmat)",
                },
            },
            "required": ["name", "phone"],
        },
    },
    {
        "name": "send_stars_invoice",
        "description": (
            "Foydalanuvchiga Telegram Stars to'lov invoice yuborish. "
            "Mijoz sotib olishga tayyor bo'lsa yoki raqamli mahsulot so'rasa chaqiring."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "Invoice yuboriladigan Telegram user ID",
                },
                "product_id": {
                    "type": "string",
                    "description": "Mahsulot ID si (config.DIGITAL_PRODUCTS dan)",
                    "enum": ["logo_template", "branding_guide"],
                },
            },
            "required": ["user_id", "product_id"],
        },
    },
    {
        "name": "forward_to_crm_group",
        "description": (
            "Mijoz ma'lumotlarini CRM Telegram guruhiga yuborish. "
            "Mijoz to'liq ma'lumotlarini bergandan so'ng (ism, telefon, xizmat turi) "
            "buni chaqiring. Sifatli lead bo'lganda majburiy."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {"type": "integer", "description": "Telegram user ID"},
                "quality": {
                    "type": "string",
                    "description": "Lead sifati",
                    "enum": ["Sifatli", "Oddiy", "Unknown", "Sifatsiz"],
                },
                "summary": {
                    "type": "string",
                    "description": "Mijoz so'rovining qisqacha bayoni",
                },
            },
            "required": ["user_id", "quality"],
        },
    },
    {
        "name": "get_user_profile",
        "description": (
            "Bazadan mijozning to'liq profilini olish. "
            "Eski mijoz bilan muloqot boshlanishida yoki avvalgi ma'lumotlar kerak bo'lsa chaqiring."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {"type": "integer", "description": "Telegram user ID"}
            },
            "required": ["user_id"],
        },
    },
    {
        "name": "get_team_members",
        "description": (
            "Agentlikning barcha inson jamoa a'zolarini va ularning rollarini olish. "
            "Kimga topshiriq berishni bilmasangiz, avval buni chaqiring."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "assign_task_to_human",
        "description": (
            "Inson jamoa a'zosiga (masalan: PM, Dizayner, CEO) yangi vazifa/topshiriq biriktirish. "
            "Mijozdan lead tushganda yoki uchrashuv so'ralganda ALBATTA topshiriq yarating."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "assigned_to": {
                    "type": "integer",
                    "description": "Vazifa biriktiriladigan xodimning Telegram ID si",
                },
                "title": {
                    "type": "string",
                    "description": "Vazifa nomi (qisqa va aniq)",
                },
                "description": {
                    "type": "string",
                    "description": "Vazifa haqida to'liq tafsilotlar",
                },
                "deadline": {
                    "type": "string",
                    "description": "Muddat (masalan: 'Bugun', 'Ertaga soat 18:00')",
                },
            },
            "required": ["assigned_to", "title", "description"],
        },
    },
    {
        "name": "sherlock_user_profile",
        "description": (
            "Mijozning Telegram profili, bio va umumiy guruhlarini tahlil qilish (Sherlock usuli). "
            "Yangi mijoz haqida ko'proq ma'lumot kerak bo'lsa yoki 'kimman?' deb so'rasa buni ishlating."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "Tahlil qilinadigan Telegram user ID",
                }
            },
            "required": ["user_id"],
        },
    },
    {
        "name": "get_crm_status_tool",
        "description": (
            "Mijozning AmoCRM dagi joriy holatini tekshirish. "
            "Agar mijoz loyiha qaysi etapda ekanligini so'rasa yoki 'status' haqida gapirsa chaqiring."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {"type": "integer", "description": "Telegram user ID"}
            },
            "required": ["user_id"],
        },
    },
    {
        "name": "update_lead_status",
        "description": (
            "AmoCRM dagi bitim (lead) statusini o'zgartirish. "
            "Muloqot yangi bosqichga o'tganda (masalan: uchrashuv belgilandi, narx so'raldi, "
            "mijoz qiziqish bildirdi) buni ALBATTA chaqiring."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {"type": "integer", "description": "Telegram user ID"},
                "status_name": {
                    "type": "string",
                    "description": "Yangi status nomi",
                    "enum": [
                        "Initial Contact",
                        "Negotiation",
                        "Qualified",
                        "Interested",
                        "Meeting Scheduled",
                        "Conversation Over",
                        "Closed Lost",
                    ],
                },
            },
            "required": ["user_id", "status_name"],
        },
    },
    {
        "name": "create_followup_task",
        "description": (
            "AmoCRM ichida lead uchun keyingi follow-up vazifasini yaratish. "
            "Mijoz keyinroq javob berishini aytsa, narx e'tirozi qolsa yoki closer follow-up kerak bo'lsa ishlatiladi."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "Telegram user ID. lead_id berilmasa shu orqali lead topiladi.",
                },
                "lead_id": {
                    "type": "integer",
                    "description": "AmoCRM lead ID. To'g'ridan-to'g'ri lead ma'lum bo'lsa ishlatiladi.",
                },
                "title": {"type": "string", "description": "Follow-up vazifa nomi"},
                "details": {
                    "type": "string",
                    "description": "Vazifa bo'yicha aniq next step yoki izoh",
                },
                "due_at": {"type": "string", "description": "ISO 8601 muddat vaqti"},
                "due_in_hours": {
                    "type": "integer",
                    "description": "Agar due_at bo'lmasa, hozirdan necha soatdan keyin bajariladi",
                },
            },
            "required": ["title"],
        },
    },
    {
        "name": "add_lead_note",
        "description": (
            "AmoCRM lead kartasiga negotiation yoki follow-up bo'yicha izoh yozish. "
            "E'tiroz, meeting natijasi yoki keyingi qadamni CRM tarixiga qoldirish uchun ishlatiladi."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "Telegram user ID. lead_id berilmasa shu orqali lead topiladi.",
                },
                "lead_id": {"type": "integer", "description": "AmoCRM lead ID"},
                "note": {
                    "type": "string",
                    "description": "CRMga yoziladigan izoh matni",
                },
            },
            "required": ["note"],
        },
    },
    {
        "name": "qualify_lead",
        "description": (
            "Mijoz ma'lumotlarini (xizmat turi, manba, qiziqish darajasi) AmoCRM maydonlariga "
            "va teglarga avtomatik saqlash. Mijoz niyatini aniqlaganingizda chaqiring."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {"type": "integer", "description": "Telegram user ID"},
                "source": {
                    "type": "string",
                    "enum": ["Telegram", "Instagram", "Facebook", "Sayt"],
                },
                "service": {
                    "type": "string",
                    "enum": ["Naming", "Logo", "Brandbook", "Web", "SMM"],
                },
                "temperature": {"type": "string", "enum": ["Sovuq", "Issiq"]},
                "need": {
                    "type": "string",
                    "description": "Mijozning asosiy ehtiyoji yoki muammosi",
                },
                "budget_range": {
                    "type": "string",
                    "enum": ["< 500$", "500$ - 1500$", "1500$ - 3000$", "> 3000$"],
                },
                "tag": {
                    "type": "string",
                    "description": "Qo'shimcha teg (masalan: 'High-Intent')",
                },
            },
            "required": ["user_id"],
        },
    },
    {
        "name": "search_local_files",
        "description": "Kompyuter (lokal disk) dagi fayllarni nomi yoki kengaytmasi bo'yicha qidirish.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Fayl nomi yoki qidirilayotgan kalit so'z",
                },
                "extension": {
                    "type": "string",
                    "description": ".pdf, .docx, .jpg kabi kengaytma (ixtiyoriy)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "google_drive_search",
        "description": "Google Drive dan fayllarni qidirish va ularning havolalarini topish.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Drive dan qidirilayotgan fayl nomi",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "execute_shell_safe",
        "description": "Tizimda xavfsiz terminal buyruqlarini bajarish (masalan: uptime, df, netstat).",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Bajariladigan buyruq"}
            },
            "required": ["command"],
        },
    },
    {
        "name": "search_crm_leads",
        "description": (
            "AmoCRM da lidlarni qidirish. "
            "Jamoa guruhida 'Abdulladan to'lov keldimi', 'Nike loyihasi qayerda', "
            "'bugun nechta yangi lid bor' kabi savollarda BU TOOLNI CHAQIRING."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Qidiruv matni: mijoz ismi, kompaniya yoki telefon",
                },
                "limit": {
                    "type": "integer",
                    "description": "Nechta natija qaytarilsin (default: 5)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_airtable_projects",
        "description": (
            "Airtable dan loyihalar ro'yxatini olish. "
            "Loyiha holati, deadline, mas'ul xodim haqida so'ralganda BU TOOLNI CHAQIRING."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "stage_filter": {
                    "type": "string",
                    "description": "Bosqich bo'yicha filtrlash (masalan: 'Aktiv', 'Tugallangan')",
                },
                "limit": {
                    "type": "integer",
                    "description": "Nechta loyiha qaytarilsin (default: 10)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_today_stats",
        "description": (
            "Bugungi statistikani olish: yangi lidlar soni, aktiv bitimlar, "
            "muddati o'tgan loyihalar. Kunlik holat so'ralganda BU TOOLNI CHAQIRING."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]


# ==================== TOOL EXECUTOR ====================



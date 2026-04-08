"""
AI Agent Tools — Gemini Function Calling uchun barcha toollar.

Bu modul botni chatbot darajasidan AI Agent darajasiga ko'taradi.
Gemini o'zi qaysi tool ni qachon ishlatishini hal qiladi va chaqiradi.
"""
import json
import logging
import datetime
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
                    "description": "Telegram foydalanuvchi ID si"
                },
                "name": {
                    "type": "string",
                    "description": "Mijoz ismi (Telegram ismi yoki o'zi aytgan ism)"
                },
                "phone": {
                    "type": "string",
                    "description": "Telefon raqam (+998XXXXXXXXX formatida)"
                },
                "business_type": {
                    "type": "string",
                    "description": "Biznes turi (restoran, salon, do'kon va h.k.)"
                },
                "region": {
                    "type": "string",
                    "description": "Hudud yoki shahar (Toshkent, Samarqand va h.k.)"
                },
                "brand_name": {
                    "type": "string",
                    "description": "Brend yoki kompaniya nomi"
                },
                "service_type": {
                    "type": "string",
                    "description": "Kerakli xizmat (logo, naming, branding strategiya va h.k.)"
                },
                "deadline": {
                    "type": "string",
                    "description": "Muddat yoki sana (masalan: '2 hafta', '1 mart')"
                },
                "lead_quality": {
                    "type": "string",
                    "description": "Lead sifati: 'Sifatli', 'Oddiy', yoki 'Unknown'",
                    "enum": ["Sifatli", "Oddiy", "Unknown", "Sifatsiz"]
                }
            },
            "required": ["user_id"]
        }
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
                    "description": "Uchrashuv mavzusi yoki nomi"
                },
                "start_time": {
                    "type": "string",
                    "description": "Boshlanish vaqti ISO 8601 formatida (masalan: '2026-03-13T14:00:00')"
                },
                "end_time": {
                    "type": "string",
                    "description": "Tugash vaqti ISO 8601 formatida. Ko'rsatilmasa, 1 soat qo'shiladi."
                },
                "description": {
                    "type": "string",
                    "description": "Uchrashuv tavsifi yoki qo'shimcha ma'lumot"
                }
            },
            "required": ["summary", "start_time"]
        }
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
                "name": {
                    "type": "string",
                    "description": "Mijoz ismi"
                },
                "phone": {
                    "type": "string",
                    "description": "Telefon raqam"
                },
                "note": {
                    "type": "string",
                    "description": "Qo'shimcha izoh (masalan: kerakli xizmat)"
                }
            },
            "required": ["name", "phone"]
        }
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
                    "description": "Invoice yuboriladigan Telegram user ID"
                },
                "product_id": {
                    "type": "string",
                    "description": "Mahsulot ID si (config.DIGITAL_PRODUCTS dan)",
                    "enum": ["logo_template", "branding_guide"]
                }
            },
            "required": ["user_id", "product_id"]
        }
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
                "user_id": {
                    "type": "integer",
                    "description": "Telegram user ID"
                },
                "quality": {
                    "type": "string",
                    "description": "Lead sifati",
                    "enum": ["Sifatli", "Oddiy", "Unknown", "Sifatsiz"]
                },
                "summary": {
                    "type": "string",
                    "description": "Mijoz so'rovining qisqacha bayoni"
                }
            },
            "required": ["user_id", "quality"]
        }
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
                "user_id": {
                    "type": "integer",
                    "description": "Telegram user ID"
                }
            },
            "required": ["user_id"]
        }
    },
    {
        "name": "get_team_members",
        "description": (
            "Agentlikning barcha inson jamoa a'zolarini va ularning rollarini olish. "
            "Kimga topshiriq berishni bilmasangiz, avval buni chaqiring."
        ),
        "parameters": {
            "type": "object",
            "properties": {}
        }
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
                    "description": "Vazifa biriktiriladigan xodimning Telegram ID si"
                },
                "title": {
                    "type": "string",
                    "description": "Vazifa nomi (qisqa va aniq)"
                },
                "description": {
                    "type": "string",
                    "description": "Vazifa haqida to'liq tafsilotlar"
                },
                "deadline": {
                    "type": "string",
                    "description": "Muddat (masalan: 'Bugun', 'Ertaga soat 18:00')"
                }
            },
            "required": ["assigned_to", "title", "description"]
        }
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
                    "description": "Tahlil qilinadigan Telegram user ID"
                }
            },
            "required": ["user_id"]
        }
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
                "user_id": {
                    "type": "integer",
                    "description": "Telegram user ID"
                }
            },
            "required": ["user_id"]
        }
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
                "user_id": {
                    "type": "integer",
                    "description": "Telegram user ID"
                },
                "status_name": {
                    "type": "string",
                    "description": "Yangi status nomi",
                    "enum": ["Initial Contact", "Qualified", "Interested", "Meeting Scheduled", "Closed Lost"]
                }
            },
            "required": ["user_id", "status_name"]
        }
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
                "source": {"type": "string", "enum": ["Telegram", "Instagram", "Facebook", "Sayt"]},
                "service": {"type": "string", "enum": ["Naming", "Logo", "Brandbook", "Web", "SMM"]},
                "temperature": {"type": "string", "enum": ["Sovuq", "Issiq"]},
                "need": {"type": "string", "description": "Mijozning asosiy ehtiyoji yoki muammosi"},
                "budget_range": {"type": "string", "enum": ["< 500$", "500$ - 1500$", "1500$ - 3000$", "> 3000$"]},
                "tag": {"type": "string", "description": "Qo'shimcha teg (masalan: 'High-Intent')"}
            },
            "required": ["user_id"]
        }
    },
    {
        "name": "search_local_files",
        "description": "Kompyuter (lokal disk) dagi fayllarni nomi yoki kengaytmasi bo'yicha qidirish.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Fayl nomi yoki qidirilayotgan kalit so'z"},
                "extension": {"type": "string", "description": ".pdf, .docx, .jpg kabi kengaytma (ixtiyoriy)"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "google_drive_search",
        "description": "Google Drive dan fayllarni qidirish va ularning havolalarini topish.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Drive dan qidirilayotgan fayl nomi"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "execute_shell_safe",
        "description": "Tizimda xavfsiz terminal buyruqlarini bajarish (masalan: uptime, df, netstat).",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Bajariladigan buyruq"}
            },
            "required": ["command"]
        }
    }
]


# ==================== TOOL EXECUTOR ====================

class AgentToolExecutor:
    """Gemini chaqirgan tool larni bajaruvchi sinf."""

    def __init__(self, db, gcontacts, gcalendar, gsheet, amocrm, bot_app, config):
        self.db = db
        self.gcontacts = gcontacts
        self.gcalendar = gcalendar
        self.gsheet = gsheet
        self.amocrm = amocrm
        self.bot_app = bot_app  # Telegram Application (bot.send_message uchun)
        self.config = config
        self._scouter = None

    async def execute(self, function_name: str, function_args: dict, context_user_id: Optional[int] = None) -> Dict[str, Any]:
        """Gemini chaqirgan tool ni bajarish va natijani qaytarish."""
        logger.info(f"[AGENT TOOL] Executing: {function_name}({function_args})")
        try:
            if function_name == "save_lead_info":
                return await self._save_lead_info(**function_args)
            elif function_name == "create_calendar_event":
                return await self._create_calendar_event(**function_args)
            elif function_name == "save_google_contact":
                return await self._save_google_contact(**function_args)
            elif function_name == "send_stars_invoice":
                return await self._send_stars_invoice(**function_args)
            elif function_name == "forward_to_crm_group":
                return await self._forward_to_crm_group(**function_args)
            elif function_name == "get_user_profile":
                return await self._get_user_profile(**function_args)
            elif function_name == "get_team_members":
                return await self._get_team_members()
            elif function_name == "assign_task_to_human":
                return await self._assign_task_to_human(**function_args)
            elif function_name == "sherlock_user_profile":
                return await self._sherlock_user_profile(**function_args)
            elif function_name == "get_crm_status_tool":
                return await self._get_crm_status_tool(**function_args)
            elif function_name == "update_lead_status":
                return await self._update_lead_status(**function_args)
            elif function_name == "qualify_lead":
                return await self._qualify_lead(**function_args)
            elif function_name == "search_local_files":
                return await self._search_local_files(**function_args)
            elif function_name == "google_drive_search":
                return await self._google_drive_search(**function_args)
            elif function_name == "execute_shell_safe":
                return await self._execute_shell_safe(**function_args)
            else:
                return {"success": False, "error": f"Unknown tool: {function_name}"}
        except Exception as e:
            logger.error(f"[AGENT TOOL ERROR] {function_name}: {e}")
            self._log_action(context_user_id, function_name, function_args, success=False, error=str(e))
            return {"success": False, "error": str(e)}

    # ---- Tool Implementations ----

    async def _save_lead_info(self, user_id: int, name: Optional[str] = None, phone: Optional[str] = None,
                               business_type: Optional[str] = None, region: Optional[str] = None,
                               brand_name: Optional[str] = None, service_type: Optional[str] = None,
                               deadline: Optional[str] = None, lead_quality: Optional[str] = None) -> Dict[str, Any]:
        """Mijoz ma'lumotlarini SQLite va Google Sheets ga saqlash."""
        import asyncio
        saved_fields = []

        # SQLite
        try:
            kwargs = {}
            if business_type: kwargs["business_type"] = business_type
            if region: kwargs["region"] = region
            if brand_name: kwargs["brand_name"] = brand_name
            if service_type: kwargs["service_type"] = service_type
            if deadline: kwargs["deadline"] = deadline

            await asyncio.to_thread(
                self.db.upsert_user, user_id, name or "Unknown", None, phone, **kwargs
            )
            saved_fields.append("SQLite DB")
        except Exception as e:
            logger.error(f"[TOOL] save_lead_info SQLite xato: {e}")

        # Google Sheets
        try:
            await asyncio.to_thread(
                self.gsheet.sync_user, 
                user_id, 
                name or "Unknown", 
                None, 
                phone=phone,
                business_type=business_type,
                region=region,
                brand_name=brand_name,
                service_type=service_type,
                deadline=deadline
            )
            saved_fields.append("Google Sheets")
        except Exception as e:
            logger.error(f"[TOOL] save_lead_info GSheets xato: {e}")

        # AmoCRM
        try:
            if phone:
                await asyncio.to_thread(
                    self.amocrm.create_lead, name or f"User {user_id}", phone, price=0, note=f"Biznes: {business_type}, Hudud: {region}"
                )
                saved_fields.append("AmoCRM")
        except Exception as e:
            logger.error(f"[TOOL] save_lead_info AmoCRM xato: {e}")

        # Agent action log
        self._log_action(user_id, "save_lead_info", {
            "name": name, "phone": phone, "business_type": business_type,
            "lead_quality": lead_quality
        }, success=True)

        return {
            "success": True,
            "message": f"Ma'lumotlar saqlandi: {', '.join(saved_fields)}",
            "saved": {
                "name": name, "phone": phone, "business_type": business_type,
                "region": region, "lead_quality": lead_quality
            }
        }

    async def _create_calendar_event(self, summary: str, start_time: str,
                                      end_time: Optional[str] = None, description: Optional[str] = None) -> Dict[str, Any]:
        """Google Calendar da tadbir yaratish."""
        import asyncio

        # Tugash vaqti yo'q bo'lsa, 1 soat qo'shish
        if not end_time:
            try:
                start_dt = datetime.datetime.fromisoformat(start_time)
                end_time = (start_dt + datetime.timedelta(hours=1)).isoformat()
            except Exception:
                end_time = start_time

        try:
            result = await asyncio.to_thread(
                self.gcalendar.create_event,
                summary=summary,
                start_time=start_time,
                end_time=end_time,
                description=description or ""
            )
            self._log_action(None, "create_calendar_event", {
                "summary": summary, "start_time": start_time
            }, success=True)
            return {
                "success": True,
                "message": f"Tadbir yaratildi: '{summary}' — {start_time}",
                "event": result
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _save_google_contact(self, name: str, phone: str, note: Optional[str] = None) -> Dict[str, Any]:
        """Google Contacts ga kontakt saqlash."""
        import asyncio
        try:
            await asyncio.to_thread(
                self.gcontacts.create_contact,
                first_name=name,
                phone=phone,
                note=note or "Telegram orqali — AI Agent tomonidan saqlandi"
            )
            self._log_action(None, "save_google_contact", {"name": name, "phone": phone}, success=True)
            return {
                "success": True,
                "message": f"Google Contacts ga saqlandi: {name} ({phone})"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _send_stars_invoice(self, user_id: int, product_id: str) -> Dict[str, Any]:
        """Telegram Stars invoice yuborish (bot.send_invoice)."""
        # Bu amal userbot.py dagi context.bot ga muhtoj.
        # Shuning uchun bu tool faqat "pending" ni qaytaradi,
        # va userbot.py o'zi invoice yuboradi.
        products = getattr(self.config, 'DIGITAL_PRODUCTS', {})
        p_info = products.get(product_id, {})
        if not p_info:
            return {"success": False, "error": f"Mahsulot topilmadi: {product_id}"}

        # DB ga log
        try:
            self.db.log_purchase(user_id, product_id, p_info.get("price", 0))
        except Exception as e:
            logger.warning(f"[TOOL] Stars purchase log xato: {e}")

        self._log_action(user_id, "send_stars_invoice", {
            "product_id": product_id, "price": p_info.get("price")
        }, success=True)

        return {
            "success": True,
            "pending_action": "send_invoice",
            "user_id": user_id,
            "product_id": product_id,
            "product_title": p_info.get("title", "Mahsulot"),
            "price": p_info.get("price", 0),
            "message": f"Invoice tayyor: {p_info.get('title')} — {p_info.get('price')} Stars"
        }

    async def _forward_to_crm_group(self, user_id: int, quality: str, summary: Optional[str] = None) -> Dict[str, Any]:
        """CRM Telegram guruhiga lead yuborish."""
        import asyncio
        crm_group_id = getattr(self.config, 'CRM_GROUP_ID', None)
        crm_topic_id = getattr(self.config, 'CRM_TOPIC_ID', None)

        if not crm_group_id:
            return {"success": False, "error": "CRM_GROUP_ID sozlanmagan"}

        # Bazadan mijoz ma'lumotlarini olish
        user_data = self.db.get_user_info(user_id) or {}
        name = user_data.get('first_name', 'Noma\'lum')
        phone = user_data.get('phone', '—')
        username = user_data.get('username', '')
        business = user_data.get('business_type', '—')
        service = user_data.get('service_type', '—')

        quality_emoji = {"Sifatli": "🔥", "Oddiy": "✅", "Unknown": "🔸", "Sifatsiz": "❌"}.get(quality, "🔸")

        crm_msg = (
            f"{quality_emoji} <b>{quality.upper()} LEAD</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>Mijoz:</b> {name}"
            f"{(' (@' + username + ')') if username else ''}\n"
            f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
            f"📞 <b>Telefon:</b> {phone}\n"
            f"💼 <b>Biznes:</b> {business}\n"
            f"🎯 <b>Xizmat:</b> {service}\n"
        )
        if summary:
            crm_msg += f"━━━━━━━━━━━━━━━━━━━━\n💬 <b>Qisqacha:</b> <i>{summary}</i>"

        try:
            # Topic ID mantiqi: Agar lead uchun maxsus topic bo'lsa, o'shanga yuborish
            # Hozircha default topic_id config dan olinadi
            topic_id = crm_topic_id
            
            await self.bot_app.bot.send_message(
                chat_id=crm_group_id,
                text=crm_msg,
                parse_mode="HTML",
                message_thread_id=topic_id
            )
            # Mark as forwarded
            await asyncio.to_thread(self.db.mark_lead_forwarded, user_id)
            self._log_action(user_id, "forward_to_crm_group", {"quality": quality}, success=True)
            return {"success": True, "message": f"CRM guruhiga yuborildi ({quality})"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _get_crm_status_tool(self, user_id: int) -> Dict[str, Any]:
        """AmoCRM dan lead holatini olib kelish."""
        user_info = self.db.get_user_info(user_id)
        phone = user_info.get("phone") if user_info else None
        
        if not phone:
            return {"success": False, "error": "Foydalanuvchi telefoni topilmadi. Avval raqamni saqlang."}
            
        try:
            from src.services.crm_service import CRMService
            crm = CRMService()
            status = await crm.get_user_context(phone)
            return {"success": True, "status": status}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _update_lead_status(self, user_id: int, status_name: str) -> Dict[str, Any]:
        """AmoCRM da bitim statusini o'zgartirish."""
        import asyncio
        user_info = self.db.get_user_info(user_id)
        phone = user_info.get("phone") if user_info else None
        
        if not phone:
            return {"success": False, "error": "Raqam yo'q - status o'zgartirilmadi."}
            
        # Hunter Pipeline (ID: 10117998)
        hunter_id = 10117998
        status_map = {
            "Initial Contact": {"id": 80178218, "pid": hunter_id, "name": "Malakalash kutilmoqda"}, 
            "Negotiation": {"id": 80178222, "pid": hunter_id, "name": "Muloqot boshlandi"},
            "Qualified": {"id": 80178222, "pid": hunter_id, "name": "Muloqot boshlandi"},       
            "Interested": {"id": 80178226, "pid": hunter_id, "name": "Qiziqish tasdiqlandi"},      
            "Meeting Scheduled": {"id": 80178230, "pid": hunter_id, "name": "Strategik sessiya"},
            "Conversation Over": {"id": 80215318, "pid": 10123314}, # Closer pipeline: Konsultatsiya o'tdi
            "Closed Lost": {"id": 143, "pid": hunter_id}
        }
        
        status_info = status_map.get(status_name)
        if not status_info:
            return {"success": False, "error": f"Unknown status: {status_name}"}

        try:
            lead = await asyncio.to_thread(self.amocrm.get_lead_by_phone, phone)
            if lead:
                lead_id = lead.get("id")
                success = await self.amocrm.update_lead_status(lead_id, status_info["id"], status_info["pid"])
                if success:
                    # Also add a note about the status change
                    await self.amocrm.add_lead_note(lead_id, f"AI statusni o'zgartirdi: {status_name}")
                    self._log_action(user_id, "update_lead_status", {"status": status_name}, success=True)
                    return {"success": True, "message": f"Status o'zgartirildi: {status_name}"}
            return {"success": False, "error": "Lead topilmadi."}
        except Exception as e:
            logger.error(f"[TOOL ERROR] update_lead_status: {e}")
            return {"success": False, "error": str(e)}


    async def _qualify_lead(self, user_id: int, source: str = None, service: str = None, 
                             temperature: str = None, need: str = None, budget_range: str = None,
                             tag: str = None) -> Dict[str, Any]:
        """AmoCRM maydonlarini va teglarini yangilash."""
        import asyncio
        user_info = self.db.get_user_info(user_id)
        phone = user_info.get("phone") if user_info else None
        
        if not phone:
            return {"success": False, "error": "Raqam yo'q - ma'lumotlar yangilanmadi."}

        fields_to_update = {}
        # Mapping Enums
        field_maps = {
            "source": {1034663: {"Telegram": 965705, "Instagram": 965707, "Facebook": 965709, "Sayt": 965703}},
            "service": {1034671: {"Naming": 965739, "Logo": 965741, "Brandbook": 965743, "Web": 965747, "SMM": 965749}},
            "temperature": {1034667: {"Sovuq": 965725, "Issiq": 965727}},
            "budget": {1427495: {"< 500$": 1262133, "500$ - 1500$": 1262135, "1500$ - 3000$": 1262137, "> 3000$": 1262139}}
        }

        if source and source in field_maps["source"][1034663]:
            fields_to_update[1034663] = field_maps["source"][1034663][source]
        if service and service in field_maps["service"][1034671]:
            fields_to_update[1034671] = field_maps["service"][1034671][service]
        if temperature and temperature in field_maps["temperature"][1034667]:
            fields_to_update[1034667] = field_maps["temperature"][1034667][temperature]
        
        # Textarea field
        if need:
            fields_to_update[1427493] = need
            
        # Select field for budget
        if budget_range and budget_range in field_maps["budget"][1427495]:
            fields_to_update[1427495] = field_maps["budget"][1427495][budget_range]

        try:
            lead = await asyncio.to_thread(self.amocrm.get_lead_by_phone, phone)
            if not lead:
                return {"success": False, "error": "Lead topilmadi."}
            
            lead_id = lead.get("id")
            results = []
            
            if fields_to_update:
                f_ok = await self.amocrm.update_lead_custom_fields(lead_id, fields_to_update)
                results.append(f"Fields: {'OK' if f_ok else 'Fail'}")
            
            if tag:
                t_ok = await self.amocrm.add_lead_tag(lead_id, tag)
                results.append(f"Tag: {'OK' if t_ok else 'Fail'}")
            elif temperature == "Issiq":
                await self.amocrm.add_lead_tag(lead_id, "High-Intent")
                results.append("Tag: High-Intent")
            
            # 3. Avtomatik Task (IDEAL PIPELINE) - Agar Issiq bo'lsa
            if temperature == "Issiq":
                import time
                deadline = int(time.time() + 3600) # 1 soat ichida bog'lanish
                await self.amocrm.create_task(lead_id, f"ISSUR: {phone} - Tezkor aloqa! (AI malakaladi)", deadline)
                # Shuningdek jamoaga xabar yuborish
                await self._assign_task_to_human(1774538344630, f"Issiq lid! Telefon: {phone}. Ehtiyoj: {need or 'aniqlanmoqda'}", "High")
                results.append("Task: Created")

            # Always add Oisha-AI tag if qualified
            await self.amocrm.add_lead_tag(lead_id, "Oisha-AI")

            return {"success": True, "message": " | ".join(results)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _get_user_profile(self, user_id: int) -> Dict[str, Any]:
        """Bazadan mijoz profilini olish."""
        import asyncio
        try:
            data = await asyncio.to_thread(self.db.get_user_info, user_id)
            if data:
                return {"success": True, "profile": data}
            else:
                return {"success": True, "profile": None, "message": "Yangi foydalanuvchi — bazada yo'q"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _get_team_members(self) -> Dict[str, Any]:
        """Jamoa a'zolarini bazadan olish."""
        import asyncio
        try:
            members = await asyncio.to_thread(self.db.get_team_roles)
            return {"success": True, "members": members}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _assign_task_to_human(self, assigned_to: int, title: str, description: str, deadline: Optional[str] = None) -> Dict[str, Any]:
        """Inson xodimga vazifa biriktirish."""
        import asyncio
        try:
            # 1. Vazifani bazaga qo'shish
            task_id = await asyncio.to_thread(
                self.db.add_task, 
                assigned_to=assigned_to, 
                description=f"{title}: {description}", 
                deadline=deadline or "Belgilanmagan"
            )
            
            # 2. Xodimga xabar yuborish
            member_info = await asyncio.to_thread(self.db.get_user_info, assigned_to)
            member_name = member_info.get("first_name", "Xodim") if member_info else "Xodim"
            
            notification = (
                f"📌 <b>Yangi Vazifa Biriktirildi!</b>\n\n"
                f"👤 <b>Xodim:</b> {member_name}\n"
                f"📝 <b>Vazifa:</b> {title}\n"
                f"📖 <b>Tafsilot:</b> {description}\n"
                f"📅 <b>Muddat:</b> {deadline or 'Tezda'}\n\n"
                f"<i>Bot tomonidan avtomatik yaratildi.</i>"
            )
            
            await self.bot_app.bot.send_message(
                chat_id=assigned_to,
                text=notification,
                parse_mode="HTML"
            )
            
            self._log_action(assigned_to, "assign_task_to_human", {"title": title}, success=True)
            return {"success": True, "message": f"Vazifa {member_name}ga biriktirildi va xabar berildi.", "task_id": task_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _sherlock_user_profile(self, user_id: int) -> Dict[str, Any]:
        """Mijozning profilini Scouter orqali tahlil qilish."""
        from src.services.scouter import Scouter
        import os
        
        if not self._scouter:
            # Session path logic
            session_path = os.path.join("data", "userbot_session")
            
            self._scouter = Scouter(session_path=session_path)

        try:
            dosye = await self._scouter.get_user_dosye(user_id)
            if dosye:
                self._log_action(user_id, "sherlock_user_profile", {"found": True}, success=True)
                return {"success": True, "dosye": dosye}
            else:
                return {"success": False, "error": "Profil ma'lumotlarini olib bo'lmadi (ehtimol maxfiylik sozalamalari tufayli)."}
        except Exception as e:
            logger.error(f"[TOOL] Sherlock error: {e}")
            return {"success": False, "error": str(e)}

    # ---- Helper ----

    def _log_action(self, user_id: Optional[int], action_type: str,
                    action_data: dict, success: bool, error: Optional[str] = None) -> None:
        """Agent amalini DB ga yozish."""
        try:
            data_json = json.dumps(action_data, ensure_ascii=False)
            if error:
                data_json = json.dumps({"data": action_data, "error": error}, ensure_ascii=False)
            self.db.log_agent_action(user_id, action_type, data_json, success)
        except Exception as e:
            logger.warning(f"[AGENT LOG] Xato: {e}")

    # ---- NEW AUTONOMOUS TOOLS (OpenClaw Style) ----

    async def _search_local_files(self, query: str, extension: Optional[str] = None) -> Dict[str, Any]:
        """Lokal fayl tizimidan qidirish."""
        import os
        import glob
        results = []
        search_pattern = f"**/*{query}*"
        if extension:
            search_pattern += extension if extension.startswith('.') else f".{extension}"
        
        # Xavfsiz qidirish uchun loyiha papkasidan boshlaymiz
        try:
            for file in glob.glob(search_pattern, recursive=True):
                if os.path.isfile(file):
                    results.append({"name": os.path.basename(file), "path": os.path.abspath(file)})
                if len(results) > 5: break # Max 5 result
            
            return {"success": True, "files": results, "count": len(results)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _google_drive_search(self, query: str) -> Dict[str, Any]:
        """Google Drive API orqali qidirish."""
        # google_service orqali integration
        try:
            files = await asyncio.to_thread(self.google_service.search_drive_files, query)
            return {"success": True, "files": files}
        except Exception as e:
            return {"success": False, "error": f"Google Drive xatosi: {e}"}

    async def _execute_shell_safe(self, command: str) -> Dict[str, Any]:
        """Faqat ma'lum (whitelist) buyruqlarni bajarish."""
        import subprocess
        allowed_commands = ["uptime", "df -h", "free -m", "ls -la", "date", "dir"]
        
        base_cmd = command.split()[0]
        if base_cmd not in [c.split()[0] for c in allowed_commands]:
            return {"success": False, "error": "Xavfsizlik! Bu buyruqni bajarishga ruxsat yo'q."}
        
        try:
            result = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT).decode()
            return {"success": True, "output": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

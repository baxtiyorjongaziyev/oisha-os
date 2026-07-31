import asyncio
from datetime import datetime, timezone
import structlog
from src.settings import settings
from src.services.core.crm.amocrm_sync import AmoCRMSync

logger = structlog.get_logger(__name__)

async def check_and_notify_remaining_payments(bot=None) -> None:
    """
    Har kuni ertalab qoldiq to'lovi sanasi kelgan yoki o'tib ketgan 
    loyihalarni (leads) aniqlab, Jamoa guruhiga eslatma yuboradi.
    """
    logger.info("Qoldiq to'lovlarni tekshirish boshlandi...")
    
    try:
        amocrm = AmoCRMSync(
            subdomain=settings.AMOCRM_SUBDOMAIN.get_secret_value() if hasattr(settings.AMOCRM_SUBDOMAIN, 'get_secret_value') else settings.AMOCRM_SUBDOMAIN,
            client_id=settings.AMOCRM_CLIENT_ID.get_secret_value() if hasattr(settings.AMOCRM_CLIENT_ID, 'get_secret_value') else settings.AMOCRM_CLIENT_ID,
            client_secret=settings.AMOCRM_CLIENT_SECRET.get_secret_value() if hasattr(settings.AMOCRM_CLIENT_SECRET, 'get_secret_value') else settings.AMOCRM_CLIENT_SECRET,
            redirect_url=settings.AMOCRM_REDIRECT_URL.get_secret_value() if hasattr(settings.AMOCRM_REDIRECT_URL, 'get_secret_value') else settings.AMOCRM_REDIRECT_URL,
        )
        
        if not amocrm.access_token:
            amocrm._load_token()
            
        if not amocrm.access_token:
            logger.error("AmoCRM token topilmadi, qoldiq to'lovlarni tekshirib bo'lmaydi.")
            return

        # Barcha ochiq bitimlarni olish
        leads = await amocrm.get_leads_detailed(limit=100)
        
        today = datetime.now().date()
        reminders = []
        
        for lead in leads:
            lead_id = lead.get("id")
            lead_name = lead.get("name", f"Lead #{lead_id}")
            custom_fields = lead.get("custom_fields_values")
            
            if not custom_fields:
                continue
                
            payment_date = None
            total_summa = lead.get("price", 0)
            
            for field in custom_fields:
                field_name = str(field.get("field_name", "")).lower()
                # "Qoldiq to'lov sanasi" yoki shunga o'xshash sana maydonini topish
                if "qoldiq" in field_name and "sana" in field_name:
                    values = field.get("values", [])
                    if values and isinstance(values, list) and values[0].get("value"):
                        # AmoCRM sanani Unix timestamp (int) tarzida beradi 
                        timestamp = values[0].get("value")
                        try:
                            timestamp = int(timestamp)
                            payment_date = datetime.fromtimestamp(timestamp).date()
                        except (ValueError, TypeError):
                            pass
            
            if payment_date:
                # Agar to'lov sanasi kelgan bo'lsa yoki o'tib ketgan bo'lsa
                if payment_date <= today:
                    diff = (today - payment_date).days
                    day_text = "Bugun" if diff == 0 else f"{diff} kun o'tdi"
                    reminders.append(f"• <b>{lead_name}</b> ({day_text})\n  Summa: {total_summa:,} UZS\n  Mijoz kartochkasi: <a href='https://{amocrm.subdomain}.amocrm.ru/leads/detail/{lead_id}'>Havola</a>")
        
        if reminders and bot:
            message = "⚠️ <b>DIQQAT: QOLDIQ TO'LOVLAR!</b>\n\nQuyidagi loyihalar bo'yicha qoldiq to'lov sanasi keldi yoki o'tib ketdi. Iltimos, mijoz bilan bog'laning:\n\n"
            message += "\n\n".join(reminders)
            
            group_id = settings.TELEGRAM_TEAM_GROUP_ID
            if group_id:
                try:
                    await bot.send_message(chat_id=group_id, text=message, parse_mode="HTML")
                    logger.info(f"Eslatma jamoa guruhiga yuborildi ({len(reminders)} ta bitim).")
                except Exception as e:
                    logger.error(f"Xabar yuborishda xatolik: {e}")
            else:
                logger.warning("TELEGRAM_TEAM_GROUP_ID topilmadi.")
        else:
            if not reminders:
                logger.info("Bugungi kunda qoldiq to'lovi kutilayotgan bitimlar topilmadi.")
                
    except Exception as e:
        logger.error(f"check_and_notify_remaining_payments xatolik: {e}", exc_info=True)

if __name__ == "__main__":
    # Test uchun
    asyncio.run(check_and_notify_remaining_payments())

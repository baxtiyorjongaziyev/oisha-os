
import re
import json
import logging
import asyncio
import datetime
import time
import random
from typing import Optional, List, Dict, Any
from telegram import LabeledPrice

logger = logging.getLogger(__name__)

class ActionParser:
    """Parses and executes [TAG:...] actions from AI responses."""

    def __init__(self, db, gcontacts, gcalendar, invoicer, amocrm, config, lead_scraper=None, bot_app=None):
        self.db = db
        self.gcontacts = gcontacts
        self.gcalendar = gcalendar
        self.invoicer = invoicer
        self.amocrm = amocrm
        self.config = config
        self.lead_scraper = lead_scraper
        self.bot_app = bot_app

    async def parse_and_execute(self, reply_text: str, sender_id: int, sender_name: str, username: str, saved_phone: str, context, is_business: bool, msg_business_connection_id: Optional[str] = None) -> str:
        """Parses all tags and executes their specific side-effects. Returns cleaned text."""
        
        # 1. Lead Quality Analysis
        lead_quality = None
        lead_match = re.search(r'\[LEAD_REPORT:\s*QUALITY\s*=\s*(.*?)\]', reply_text, re.IGNORECASE)
        if lead_match:
            lead_quality = str(lead_match.group(1)).strip().lower()
        
        closing_phrase = "Baxtiyorjon tez orada siz bilan bog'lanadi"
        if closing_phrase in reply_text and not lead_quality:
            lead_quality = "sifatli"

        # 2. CONTACT_INFO
        contact_match = re.search(r'\[CONTACT_INFO:\s*(.*?)\]', reply_text, re.IGNORECASE)
        if contact_match:
            try:
                contact_raw = str(contact_match.group(1) or "")
                c_data = {}
                for part in contact_raw.split('|'):
                    if '=' in part:
                        k_v = part.split('=', 1)
                        if len(k_v) == 2:
                            c_data[k_v[0].strip()] = k_v[1].strip()
                
                if c_data.get('name') or c_data.get('phone'):
                    self.gcontacts.create_contact(
                        first_name=c_data.get('name', 'Noma\'lum'),
                        phone=c_data.get('phone', ''),
                        note=c_data.get('note', 'Telegram orqali avtomatik saqlandi')
                    )
            except Exception as ce:
                logger.error(f"[ACTION_PARSER] Contact parsing error: {ce}")
            reply_text = re.sub(r'\[CONTACT_INFO:.*?\]', '', reply_text).strip()

        # 3. SAVE_INFO
        save_info_matches = re.finditer(r'\[SAVE_INFO:\s*(.*?)\]', reply_text, re.IGNORECASE)
        has_updates = False
        update_data = {}
        for match in save_info_matches:
            try:
                info_raw = str(match.group(1) or "")
                if '=' in info_raw:
                    k_v = info_raw.split('=', 1)
                    if len(k_v) == 2:
                        k, v = k_v[0].strip().lower(), k_v[1].strip()
                        update_data[k] = v
                        has_updates = True
            except Exception as e:
                logger.error(f"[ACTION_PARSER] SAVE_INFO parsing error: {e}")
        
        if has_updates:
            self.db.upsert_user(sender_id, sender_name, username=username, **update_data)
            reply_text = re.sub(r'\[SAVE_INFO:.*?\]', '', reply_text, flags=re.IGNORECASE).strip()

        # 4. CALENDAR_EVENT
        calendar_match = re.search(r'\[CALENDAR_EVENT:\s*(.*?)\]', reply_text, re.IGNORECASE)
        if calendar_match:
            try:
                cal_raw = str(calendar_match.group(1) or "")
                cal_data = {}
                for part in cal_raw.split('|'):
                    if '=' in part:
                        k_v = part.split('=', 1)
                        if len(k_v) == 2:
                            cal_data[k_v[0].strip()] = k_v[1].strip()
                
                if cal_data.get('summary') and cal_data.get('start'):
                    start_str = cal_data.get('start')
                    end_str = cal_data.get('end')
                    if not end_str:
                        try:
                            import datetime as dt_mod
                            start_dt = dt_mod.datetime.fromisoformat(str(start_str))
                            end_str = (start_dt + dt_mod.timedelta(hours=1)).isoformat()
                        except:
                            end_str = start_str
                    
                    self.gcalendar.create_event(
                        summary=cal_data.get('summary'),
                        start_time=start_str,
                        end_time=end_str,
                        description=cal_data.get('description', '')
                    )
                    self.db.update_meeting(sender_id, start_str)
                    
                    # Notify CRM Group
                    if self.config.CRM_GROUP_ID:
                        crm_msg = (
                            f"📅 <b>YANGI UCHRASHUV BELGILANDI!</b>\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n"
                            f"👤 <b>Mijoz:</b> {sender_name} (@{username or 'yoq'})\n"
                            f"🕒 <b>Vaqti:</b> {start_str}\n"
                            f"📝 <b>Mavzu:</b> {cal_data.get('summary', '...')} \n"
                        )
                        asyncio.create_task(context.bot.send_message(chat_id=self.config.CRM_GROUP_ID, text=crm_msg, parse_mode="HTML"))
            except Exception as e:
                logger.error(f"[ACTION_PARSER] Calendar parsing error: {e}")
            reply_text = re.sub(r'\[CALENDAR_EVENT:.*?\]', '', reply_text).strip()

        # 5. SELL_STARS
        stars_match = re.search(r'\[SELL_STARS:\s*(.*?)\]', reply_text, re.IGNORECASE)
        if stars_match:
            try:
                stars_raw = str(stars_match.group(1) or "")
                s_data = {}
                for part in stars_raw.split('|'):
                    if '=' in part:
                        k_v = part.split('=', 1)
                        if len(k_v) == 2:
                            s_data[k_v[0].strip()] = k_v[1].strip()
                
                p_id = s_data.get('id')
                p_title = str(s_data.get('title', 'Raqamli mahsulot'))
                p_price = int(s_data.get('price', 0))
                
                if p_id and p_price > 0:
                    self.db.log_purchase(sender_id, p_id, p_price)
                    await context.bot.send_invoice(
                        chat_id=sender_id,
                        title=p_title,
                        description=f"{p_title} uchun to'lov",
                        payload=f"stars_pay_{p_id}",
                        provider_token="",
                        currency="XTR",
                        prices=[LabeledPrice(p_title, p_price)]
                    )
            except Exception as e:
                logger.error(f"[ACTION_PARSER] Stars parsing error: {e}")
            reply_text = re.sub(r'\[SELL_STARS:.*?\]', '', reply_text).strip()

        # 6. GENERATE_INVOICE
        invoice_match = re.search(r'\[GENERATE_INVOICE:\s*(.*?)\|?(.*?)?\]', reply_text, re.IGNORECASE)
        if invoice_match:
            try:
                inv_sum_raw = invoice_match.group(1).strip()
                inv_desc = (invoice_match.group(2) or "Xizmatlar to'lovi").strip()
                inv_sum = int(re.sub(r'\D', '', inv_sum_raw))
                
                random_id = str(random.randint(1000, 9999))
                invoice_path = self.invoicer.generate_invoice(
                    user_name=sender_name,
                    product_name=inv_desc,
                    price_stars=f"{inv_sum:,} UZS",
                    purchase_id=random_id
                )
                
                caption = f"🧾 **Sizning Hisob-fakturangiz**\nSumma: {inv_sum:,} UZS"
                if is_business:
                    await context.bot.send_document(
                        chat_id=sender_id, # Assuming this works for business connection
                        document=open(invoice_path, "rb"),
                        caption=caption,
                        parse_mode="Markdown",
                        business_connection_id=msg_business_connection_id
                    )
                else:
                    await context.bot.send_document(
                        chat_id=sender_id,
                        document=open(invoice_path, "rb"),
                        caption=caption,
                        parse_mode="Markdown"
                    )
            except Exception as e:
                logger.error(f"[ACTION_PARSER] Invoice parsing error: {e}")
            reply_text = re.sub(r'\[GENERATE_INVOICE:.*?\]', '', reply_text).strip()
            
        # 7. AMO_LEAD (Lead creation/sync)
        amo_lead_match = re.search(r'\[AMO_LEAD:\s*(.*?)\]', reply_text, re.IGNORECASE)
        if amo_lead_match:
            try:
                amo_raw = str(amo_lead_match.group(1) or "")
                amo_data = {}
                for part in amo_raw.split('|'):
                    if '=' in part:
                        k_v = part.split('=', 1)
                        if len(k_v) == 2:
                            amo_data[k_v[0].strip().lower()] = k_v[1].strip()
                
                lead_name = amo_data.get('name') or sender_name
                lead_phone = amo_data.get('phone') or saved_phone
                lead_note = amo_data.get('note', 'Telegram orqali avtomatik lead')
                
                if lead_phone and lead_phone != "Raqam yo'q":
                    # Run lead creation in background
                    async def run_amo_sync():
                        l_id = await self.amocrm.ensure_lead(lead_name, lead_phone, lead_note)
                        if l_id and self.config.CRM_GROUP_ID:
                            # Notify CRM Group
                            crm_msg = (
                                f"🔥 <b>YANGI LEAD AMOCRM-GA TUSHDI!</b>\n"
                                f"━━━━━━━━━━━━━━━━━━━━\n"
                                f"👤 <b>Mijoz:</b> {lead_name}\n"
                                f"📞 <b>Tel:</b> <code>{lead_phone}</code>\n"
                                f"📝 <b>Izoh:</b> {lead_note}\n"
                                f"🔗 <a href='https://{self.config.AMOCRM_SUBDOMAIN}.amocrm.ru/leads/detail/{l_id}'>Bitimni ko'rish</a>"
                            )
                            await context.bot.send_message(chat_id=self.config.CRM_GROUP_ID, text=crm_msg, parse_mode="HTML")
                    
                    asyncio.create_task(run_amo_sync())
            except Exception as e:
                logger.error(f"[ACTION_PARSER] AMO_LEAD parsing error: {e}")
            reply_text = re.sub(r'\[AMO_LEAD:.*?\]', '', reply_text, flags=re.IGNORECASE).strip()

        # 8. SYNC_LEADS
        sync_match = re.search(r'\[SYNC_LEADS:\s*topic=(\d+)\|?(limit=(\d+))?\]', reply_text, re.IGNORECASE)
        if sync_match and self.lead_scraper:
            try:
                topic_id = int(sync_match.group(1))
                limit = int(sync_match.group(3) or 25)
                
                # Start sync in background to avoid blocking the bot response
                asyncio.create_task(self.lead_scraper.sync_topic_to_contacts(
                    client=self.lead_scraper.client, # We'll need to make sure client is available
                    group_id=self.config.MAIN_GROUP_ID, 
                    topic_id=topic_id,
                    limit=limit
                ))
                logger.info(f"[ACTION_PARSER] Lead sync started for topic {topic_id} (limit={limit})")
            except Exception as e:
                logger.error(f"[ACTION_PARSER] Sync leads error: {e}")
            reply_text = re.sub(r'\[SYNC_LEADS:.*?\]', '', reply_text).strip()

        # Final Clean-up
        reply_text = re.sub(r'\[LEAD_REPORT:.*?\]', '', reply_text, flags=re.IGNORECASE).strip()
        reply_text = re.sub(r'\n{3,}', '\n\n', reply_text).strip()
        
        return reply_text

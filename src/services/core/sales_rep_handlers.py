"""Sotuvchi uchun Telegram bot komandalar."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

PLAYBOOK_TEXT = """\U0001f4cb *Jon Branding Sales Playbook*

*Sales bosqichlari:*
\U0001f535 Yangi so'rov → 24s ichida qo'ng'iroq
\U0001f535 Birinchi kontakt → Ehtiyojni aniqla
\U0001f535 Muloqot → Qualification (5 savol)
\U0001f7e1 Sifatli lead → Uchrashuv belgila
\U0001f7e1 Uchrashuv → Brief to'ldir
\U0001f7e0 Konsultatsiya → KP tayyorla
\U0001f7e0 Prezentatsiya → Follow-up 48s
\U0001f534 Muzokara → E'tirozlarni hal qil
\U0001f7e2 50% Avans → Farmer ga o'tkaz

*Har qo'ng'iroqdan keyin:*
1. Amo ga izoh yoz
2. Keyingi task qo'y
3. Status ni yanginla

*Qizil chiziqlar (QILMA):*
❌ 30%+ chegirma
❌ Avanssiz ish boshlash
❌ 2 haftadan ko'p javobsiz qoldirish"""

AMO_YORDAM_TEXT = """⚙️ *AmoCRM ichida qulaylik*

*Kerakli filtrlar:*
• \"Mening ochiq lidlarim\" — faqat sizniki
• \"Bugun task bor\" — bugungi vazifalar
• \"Kechikkan\" — muddat o'tganlar

*Task yozish shabloni:*
`Qo'ng'iroq | [sabab] | [muddat]`
Masalan: `Qo'ng'iroq | KP yuborildi | 14.06 18:00`

*Bosqich o'tkazish qoidasi:*
Task bajarilmasa — bosqich o'tmasin

*Asosiy voronka:* Sales pipeline
*Farmer ga o'tkazish:* 50% avans olgandan keyin"""


async def cmd_bugungi5(event, service, manager_amo_id: int):
    try:
        leads = service.get_manager_leads(manager_amo_id)
        top5 = service.get_todays_top5(leads)
        if not top5:
            await event.respond("✅ Bugun faol lidingiz yo'q!")
            return
        lines = [service.format_lead_line(l, i + 1) for i, l in enumerate(top5)]
        text = "\U0001f3af *Bugungi TOP-5 lidingiz:*\n\n" + "\n\n".join(lines)
        await event.respond(text, parse_mode="markdown", link_preview=False)
    except Exception as e:
        logger.error("[cmd_bugungi5] %s", e)
        await event.respond("⚠️ Ma'lumot olib bo'lmadi. Keyinroq urinib ko'ring.")


async def cmd_mening_lidlarim(event, service, manager_amo_id: int):
    try:
        leads = service.get_manager_leads(manager_amo_id)
        if not leads:
            await event.respond("✅ Sizda ochiq lid yo'q.")
            return
        lines = [service.format_lead_line(lead, i + 1) for i, lead in enumerate(leads[:20], 0)]
        text = f"\U0001f4cb *Sizning ochiq lidlaringiz* ({len(leads)} ta):\n\n" + "\n\n".join(lines)
        if len(leads) > 20:
            text += f"\n\n...va yana {len(leads) - 20} ta"
        await event.respond(text, parse_mode="markdown", link_preview=False)
    except Exception as e:
        logger.error("[cmd_mening_lidlarim] %s", e)
        await event.respond("⚠️ Xatolik yuz berdi.")


async def cmd_keyingi_vazifa(event, service, manager_amo_id: int):
    try:
        leads = service.get_manager_leads(manager_amo_id)
        top5 = service.get_todays_top5(leads)
        if not top5:
            await event.respond("✅ Bugun vazifangiz yo'q!")
            return
        text = "⚡️ *Hozirgi eng muhim vazifangiz:*\n\n" + service.format_lead_line(top5[0], 1)
        await event.respond(text, parse_mode="markdown", link_preview=False)
    except Exception as e:
        logger.error("[cmd_keyingi_vazifa] %s", e)
        await event.respond("⚠️ Xatolik yuz berdi.")


async def cmd_playbook(event):
    await event.respond(PLAYBOOK_TEXT, parse_mode="markdown")


async def cmd_amo_yordam(event):
    await event.respond(AMO_YORDAM_TEXT, parse_mode="markdown")

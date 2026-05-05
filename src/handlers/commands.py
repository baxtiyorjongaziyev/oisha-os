import logging
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes
from settings import settings as config

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    await update.message.reply_text(
        "Va alaykum assalom! 🌟\n\n"
        "Yaxshimisiz? Sizni ko'rib turganimdan juda xursandman. "
        "Men <b>Oishaman</b> — Baxtiyorjon Gaziyevning sun'iy intellektli yordamchisi.\n\n"
        "Sizga brending, logotip dizayni yoki biznesingiz vizual qiyofasini yaratishda yordam beraman. "
        "📌 <i>Buyruqlar:</i>\n"
        "/start - Botni ishga tushirish\n"
        "/register [rol] - Jamoa a'zosi sifatida ro'yxatdan o'tish\n"
        "/portfolio — Ishlarimizni ko'rish\n"
        "/status — Loyiha holati va bot statistikasi\n"
        "/login — Telegram orqali avtorizatsiya",
        parse_mode="HTML",
    )


async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /ping command."""
    await update.message.reply_text("🏓 Pong! Bot ishlamoqda. \nHolat: ✅ Aktiv")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    keywords_list = "\n".join([f"  • {k}" for k in config.KEYWORDS.keys()])
    await update.message.reply_text(
        f"🤖 Bot haqida:\n\nKalit so'zlar:\n{keywords_list}", parse_mode="HTML"
    )


async def status_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE, db, crm=None
) -> None:
    """Handle /status command. Owner: stats, Client: CRM status."""
    user_id = update.effective_user.id

    if user_id == config.OWNER_ID:
        stats = db.get_stats()
        await update.message.reply_text(
            "📊 <b>Bot Statistikasi (Owner):</b>\n\n"
            f"👥 Mijozlar: {stats['total_users']}\n"
            f"📑 Xabarlar: {stats['total_messages']}\n"
            f"📅 Vazifalar: {stats['total_tasks']}",
            parse_mode="HTML",
        )
    else:
        # Mijoz uchun CRM dan holatni olish
        user_info = db.get_user_info(user_id)
        phone = user_info.get("phone") if user_info else None

        status_text = "Siz hali ro'yxatdan o'tmagansiz. Iltimos, telefon raqamingizni yuboring yoki /login buyrug'ini ishlating."
        if phone and crm:
            status_text = await crm.get_user_context(phone)

        await update.message.reply_text(
            f"📋 <b>Sizning loyihangiz holati:</b>\n\n{status_text}", parse_mode="HTML"
        )


async def login_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Telegram Login widget uchun havola yuborish."""
    # Odatda login widget saytda bo'ladi
    login_url = f"{config.WEBAPP_URL}/login?user_id={update.effective_user.id}"
    keyboard = [[InlineKeyboardButton("Telegram orqali kirish 🛡️", url=login_url)]]

    await update.message.reply_text(
        "<b>Telegram orqali avtorizatsiya:</b>\n\n"
        "Tizimga xavfsiz kirish va AmoCRM ma'lumotlaringizni bog'lash uchun tugmani bosing.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )


async def register_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE, db
) -> None:
    """Handle /register command."""
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text(
            "❌ Iltimos, rolni ko'rsating.\nMasalan: `/register owner`",
            parse_mode="Markdown",
        )
        return

    role = context.args[0].lower()
    if role == "owner" and user_id != config.OWNER_ID:
        await update.message.reply_text("❌ Siz bot egasi emassiz.")
        return

    db.upsert_user(
        user_id, update.effective_user.first_name, update.effective_user.username
    )
    if db.set_user_role(user_id, role):
        await update.message.reply_text(
            f"✅ Siz muvaffaqiyatli **{role}** sifatida ro'yxatdan o'tdingiz!",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text("❌ Ro'yxatdan o'tishda xatolik yuz berdi.")


async def branding_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE, ai_client, types
) -> None:
    """AI orqali branding materiallari yaratish."""
    if update.effective_user.id != config.OWNER_ID:
        return

    if not context.args:
        await update.message.reply_text("🎨 `/branding [tavsif]`", parse_mode="HTML")
        return

    prompt = " ".join(context.args)
    status_msg = await update.message.reply_text("⏳ **AI tasvir yaratmoqda...**")

    try:
        response = ai_client.models.generate_image(
            model="imagen-3.0-generate-001",
            prompt=prompt,
            config=types.GenerateImageConfig(
                number_of_images=1,
                include_rai_reason=True,
                output_mime_type="image/jpeg",
            ),
        )
        if response.generated_images:
            image_bytes = response.generated_images[0].image.image_bytes
            await update.message.reply_photo(
                photo=image_bytes, caption=f"🎨 Tavsif: _{prompt}_", parse_mode="HTML"
            )
            await status_msg.delete()
        else:
            await status_msg.edit_text("❌ Tasvir yaratib bo'lmadi.")
    except Exception as e:
        logger.error(f"[BRANDING ERROR] {e}")
        await status_msg.edit_text(f"❌ Xato: {e}")


async def task_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE, db, ai_client=None
) -> None:
    """AI-powered task assignment."""
    user_id = update.effective_user.id
    if user_id != config.OWNER_ID and not db.is_team_member(user_id):
        return

    if not context.args:
        await update.message.reply_text(
            "❌ `/task [vazifa tafsiloti]`", parse_mode="Markdown"
        )
        return

    raw_text = " ".join(context.args)

    if ai_client:
        try:
            query = f'Quyidagi matndan vazifa tafsilotlarini ajratib ol:\nMatn: {raw_text}\nJSON: {{"who":"...","task":"...","deadline":"..."}}'
            response = ai_client.models.generate_content(
                model="gemini-2.0-flash",
                contents=query,
                config={"response_mime_type": "application/json"},
            )
            data = json.loads(response.text)
            who, task_desc, deadline = (
                data.get("who"),
                data.get("task"),
                data.get("deadline"),
            )
            task_id = db.add_task(who, task_desc, deadline)
            await update.message.reply_text(
                f"📌 **YANGI VAZIFA [#{task_id}]**\nMas'ul: {who}\nTask: {task_desc}"
            )
            return
        except Exception as e:
            logger.error(f"[TASK ERROR] {e}")

    # Fallback manual
    task_id = db.add_task("Unknown", raw_text, "TBD")
    await update.message.reply_text(f"✅ Vazifa saqlandi (ID: {task_id})")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE, db) -> None:
    """Detailed stats for owner."""
    if update.effective_user.id != config.OWNER_ID:
        return
    stats = db.get_stats()
    msg = (
        f"📈 **Bot Statistikasi**\n"
        f"Mijozlar: {stats['total_users']}\n"
        f"Xabarlar: {stats['total_messages']}\n"
        f"Vazifalar: {stats['total_tasks']}"
    )
    await update.message.reply_text(msg, parse_mode="HTML")


async def portfolio_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send portfolio link."""
    keyboard = [
        [
            InlineKeyboardButton(
                "Portfelni ochish 🎨", web_app=WebAppInfo(url=config.WEBAPP_URL)
            )
        ]
    ]
    await update.message.reply_text(
        "Mening ishlarim bilan tanishing:", reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def broadcast_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE, db
) -> None:
    """Send message to all users (Owner only)."""
    if update.effective_user.id != config.OWNER_ID:
        return
    if not context.args:
        await update.message.reply_text("Format: /broadcast [xabar]")
        return

    text = " ".join(context.args)
    users = db.get_all_users()
    count = 0
    for u_id in users:
        try:
            await context.bot.send_message(chat_id=u_id, text=text)
            count += 1
            await asyncio.sleep(0.05)
        except:
            continue
    await update.message.reply_text(f"✅ {count} ta foydalanuvchiga yuborildi.")


async def unregister_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE, db
) -> None:
    """Remove user from team."""
    if update.effective_user.id != config.OWNER_ID:
        return
    if not context.args:
        return
    target_id = int(context.args[0])
    if db.set_user_role(target_id, "user"):
        await update.message.reply_text(
            f"✅ Foydalanuvchi {target_id} jamoadan chiqarildi."
        )


async def amofix_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE, amocrm
) -> None:
    """Handle /amofix command to set initial AmoCRM code."""
    if update.effective_user.id != config.OWNER_ID:
        return
    if not context.args:
        await update.message.reply_text("❌ Iltimos, AmoCRM kodini yuboring.")
        return
    auth_code = str(context.args[0])
    if amocrm.authorize_initial(auth_code):
        await update.message.reply_text("✅ AmoCRM muvaffaqiyatli ulandi!")
    else:
        await update.message.reply_text("❌ Avtorizatsiyada xato!")


async def pay_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a sample payment invoice."""
    if not config.PROVIDER_TOKEN:
        await update.message.reply_text("⚠️ To'lov tizimi ulanmagan.")
        return
    prices = [LabeledPrice("Premium Xizmat", 5000000)]
    await context.bot.send_invoice(
        update.message.chat_id,
        "Xizmat to'lovi",
        "Tavsif",
        "bot-service-payment",
        config.PROVIDER_TOKEN,
        "UZS",
        prices,
    )


async def analyze_history_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE, scouter, db, learner
) -> None:
    """Analyze history from 2025 onwards (Owner only)."""
    if str(update.effective_user.id) != str(config.OWNER_ID):
        return
    await update.message.reply_text(
        "🕵️‍♂️ 2025-yildan beri bo'lgan barcha shaxsiy suhbatlarni tahlil qilish boshlandi..."
    )
    # This would ideally be a background task
    # ... logic from userbot.py ...
    pass

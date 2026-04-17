
import logging
from telegram import Update, LabeledPrice
from telegram.ext import ContextTypes
import config

logger = logging.getLogger(__name__)

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Answer the pre-checkout query."""
    query = update.pre_checkout_query
    await query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, db, invoicer) -> None:
    """Handle successful payments and generate invoices."""
    payment = update.message.successful_payment
    user_id = update.effective_user.id
    payload = payment.invoice_payload
    
    if payload.startswith("stars_pay_"):
        product_id = payload.replace("stars_pay_", "")
        db.complete_purchase(user_id, product_id)
        
        p_info = config.DIGITAL_PRODUCTS.get(product_id, {})
        product_title = p_info.get("title", "Mahsulot")
        price = p_info.get("price", 0)
        
        try:
            invoice_path = invoicer.generate_invoice(
                user_name=update.effective_user.first_name,
                product_name=product_title,
                price_stars=price,
                purchase_id=product_id
            )
            with open(invoice_path, "rb") as pdf_file:
                await update.message.reply_document(
                    document=pdf_file,
                    caption=f"✅ **To'lov tasdiqlandi!**\n\nSizning '{product_title}' uchun hisob-fakturangiz biriktirildi.",
                    parse_mode="HTML"
                )
        except Exception as e:
            logger.error(f"[PAYMENT INVOICE ERROR] {e}")
            await update.message.reply_text(f"✅ To'lov tasdiqlandi! '{product_title}' xarid qilindi.")
            
    elif payload.startswith("invoice_pay_"):
        await update.message.reply_text("✅ To'lovingiz qabul qilindi. Rahmat!")

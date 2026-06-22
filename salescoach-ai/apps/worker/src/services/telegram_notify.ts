/**
 * Scoring tugaganda Telegram orqali menejerga xabar yuboradi.
 * oisha-os bot token ishlatadi (yoki alohida token).
 */

export async function notifyTelegramScoring(
  callId: string,
  score: number,
  customerName: string | null,
  status: 'DONE' | 'FAILED',
) {
  const token = process.env.TELEGRAM_BOT_TOKEN;
  const chatId = process.env.TELEGRAM_NOTIFY_CHAT_ID;
  const webUrl = (process.env.WEB_URL ?? 'http://localhost:3000').replace(/\/$/, '');

  if (!token || !chatId) return;

  const scoreEmoji = score >= 80 ? '🟢' : score >= 60 ? '🟡' : '🔴';

  const text =
    status === 'DONE'
      ? [
          `🎯 <b>Qo'ng'iroq tahlili tayyor!</b>`,
          ``,
          `👤 Mijoz: <b>${customerName ?? "Noma'lum"}</b>`,
          `${scoreEmoji} Ball: <b>${Math.round(score)}/100</b>`,
          ``,
          `🔗 <a href="${webUrl}/calls/${callId}">To'liq natijani ko'rish →</a>`,
        ].join('\n')
      : [
          `⚠️ <b>Qo'ng'iroq tahlili amalga oshmadi</b>`,
          ``,
          `👤 Mijoz: ${customerName ?? "Noma'lum"}`,
          `🔗 <a href="${webUrl}/calls/${callId}">Ko'rish →</a>`,
        ].join('\n');

  try {
    const res = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        chat_id: chatId,
        text,
        parse_mode: 'HTML',
        disable_web_page_preview: true,
      }),
    });
    if (!res.ok) {
      const err = await res.text().catch(() => '');
      console.warn(`[TelegramNotify] Failed: ${res.status} ${err.slice(0, 100)}`);
    }
  } catch (err: any) {
    console.warn(`[TelegramNotify] Error: ${err.message}`);
  }
}

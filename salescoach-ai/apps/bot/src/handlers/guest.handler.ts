import type { Bot, Context, RawApi } from 'grammy';

/**
 * Guest Bot handler — Telegram AI Bot Revolution feature #1.
 *
 * When `supports_guest_queries=true` is set on the bot, Telegram sends
 * `guest_message` updates whenever someone @mentions the bot in a chat
 * it hasn't joined.
 *
 * Grammy 1.34+ handles this as a regular `message` update with the
 * `guest_query_id` field present. We detect it, process the request,
 * and answer via `answerGuestQuery`.
 */

interface GuestContext extends Context {
  guestQueryId?: string;
}

export function registerGuestHandler(bot: Bot): void {
  // Handle all incoming messages that carry a guest_query_id
  bot.on('message', async (ctx) => {
    const raw = ctx.update as any;
    const guestQueryId: string | undefined =
      raw?.message?.guest_query_id ??
      raw?.guest_message?.guest_query_id;

    if (!guestQueryId) return; // not a guest query

    const text: string =
      ctx.message?.text ?? ctx.message?.caption ?? '';
    const senderName =
      ctx.from?.first_name ?? ctx.from?.username ?? 'Foydalanuvchi';

    console.log(`[guest_bot] Guest query from ${senderName}: ${text.slice(0, 80)}`);

    try {
      // Build a brief reply — in production, route through your LLM/agent
      const replyText = await generateGuestReply(text, senderName);

      await (ctx.api.raw as any).answerGuestQuery({
        guest_query_id: guestQueryId,
        result: {
          type: 'article',
          id: 'reply',
          title: 'SalesCoach javob',
          input_message_content: {
            message_text: replyText.slice(0, 4000),
            parse_mode: 'Markdown',
          },
        },
      });
    } catch (err: any) {
      console.error('[guest_bot] answerGuestQuery failed:', err.message);
    }
  });

  console.log('[guest_bot] Guest query handler registered');
}

async function generateGuestReply(text: string, senderName: string): Promise<string> {
  // Default: explain what the bot does and how to upload a call
  const lower = text.toLowerCase();

  if (lower.includes('score') || lower.includes('baho') || lower.includes('call')) {
    return (
      `Salom ${senderName}! 👋\n\n` +
      `SalesCoach — savdo qo'ng'iroqlarini tahlil qiluvchi AI.\n\n` +
      `Audio yuboring → avtomatik transkript + baho + coaching card olasiz.\n` +
      `@salescoach_bot ga to'g'ridan-to'g'ri yozing yoki audio yuboring.`
    );
  }

  return (
    `Salom ${senderName}! SalesCoach AI — savdo qo'ng'iroqlarini baholash tizimi.\n` +
    `Qo'ng'iroq audiosini yuboring, men tahlil qilib, batafsil coaching card tayyorlayman. 🎯`
  );
}

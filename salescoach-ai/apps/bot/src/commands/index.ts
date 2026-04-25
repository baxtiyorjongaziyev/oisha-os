import { Bot } from 'grammy';

export function registerCommands(bot: Bot) {
  bot.command('start', (ctx) =>
    ctx.reply(
      'Salom! Men SalesCoach AI botman.\n\n' +
      'Qo\'ng\'iroq tahlili uchun audio faylni yuboring yoki:\n' +
      '/score — oxirgi tahlil natijasini ko\'ring\n' +
      '/help — yordam',
    ),
  );

  bot.command('help', (ctx) =>
    ctx.reply(
      'SalesCoach AI — savdo qo\'ng\'iroqlari tahlilchisi\n\n' +
      'Audio faylni yuboring → transkriptsiya → baholash → hisobot',
    ),
  );

  bot.command('score', async (ctx) => {
    const apiUrl = process.env.API_URL ?? 'http://localhost:4000/v1';
    const token = process.env.BOT_API_TOKEN;
    if (!token) return ctx.reply('Bot API token not configured');

    const res = await fetch(`${apiUrl}/scorecards?limit=1`, {
      headers: { Authorization: `Bearer ${token}` },
    }).catch(() => null);

    if (!res?.ok) return ctx.reply('Could not fetch scorecard. Please log in at the web app.');

    const [scorecard] = await res.json();
    if (!scorecard) return ctx.reply('No scorecards yet. Upload a call first.');

    ctx.reply(
      `Last call score: *${Math.round(scorecard.overallScore)}/100*\n` +
      `${scorecard.call?.customerName ?? 'Unknown customer'}\n\n` +
      `${scorecard.summary}`,
      { parse_mode: 'Markdown' },
    );
  });
}

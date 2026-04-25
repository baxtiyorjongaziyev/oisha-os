import { Bot, Context } from 'grammy';

interface ScorecardItem {
  overallScore: number;
  summary: string;
  call?: { customerName?: string | null };
}

export function registerCommands(bot: Bot<Context>) {
  bot.command('start', (ctx) =>
    ctx.reply(
      'Salom! Men SalesCoach AI botman.\n\n' +
      "Qo'ng'iroq tahlili uchun audio faylni yuboring yoki:\n" +
      '/score — oxirgi tahlil natijasini ko\'ring\n' +
      '/help — yordam',
    ),
  );

  bot.command('help', (ctx) =>
    ctx.reply(
      "SalesCoach AI — savdo qo'ng'iroqlari tahlilchisi\n\n" +
      'Audio faylni yuboring → transkriptsiya → baholash → hisobot',
    ),
  );

  bot.command('score', async (ctx) => {
    const apiUrl = process.env['API_URL'] ?? 'http://localhost:4000/v1';
    const apiToken = process.env['BOT_API_TOKEN'];
    if (!apiToken) {
      await ctx.reply('Bot API token not configured');
      return;
    }

    const res = await fetch(`${apiUrl}/scorecards?limit=1`, {
      headers: { Authorization: `Bearer ${apiToken}` },
    }).catch(() => null);

    if (!res?.ok) {
      await ctx.reply('Could not fetch scorecard. Please log in at the web app.');
      return;
    }

    const data = (await res.json()) as ScorecardItem[];
    const scorecard = data[0];
    if (!scorecard) {
      await ctx.reply('No scorecards yet. Upload a call first.');
      return;
    }

    await ctx.reply(
      `Last call score: *${Math.round(scorecard.overallScore)}/100*\n` +
      `${scorecard.call?.customerName ?? 'Unknown customer'}\n\n` +
      `${scorecard.summary}`,
      { parse_mode: 'Markdown' },
    );
  });
}

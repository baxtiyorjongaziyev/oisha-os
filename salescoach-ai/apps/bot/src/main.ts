import 'dotenv/config';
import { Bot } from 'grammy';
import { registerCommands } from './commands/index.js';
import { registerHandlers } from './handlers/index.js';
import { registerGuestHandler } from './handlers/guest.handler.js';

const token = process.env['BOT_TOKEN'];
if (!token) throw new Error('BOT_TOKEN is required');

const bot = new Bot(token);

registerCommands(bot);
registerHandlers(bot);
registerGuestHandler(bot);   // Guest Bot: handle @mention queries in non-joined chats

bot.catch((err) => {
  console.error('[bot] Error:', err.message);
});

bot.start({
  onStart: (info) => {
    console.log(`[bot] SalesCoach bot @${info.username} started`);
    // Advertise guest query support via Bot API
    (bot.api.raw as any)
      .setMyDefaultAdminRights?.({})
      .catch(() => {});
  },
});

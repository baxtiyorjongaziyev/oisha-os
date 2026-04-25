import 'dotenv/config';
import { Bot } from 'grammy';
import { registerCommands } from './commands/index.js';
import { registerHandlers } from './handlers/index.js';

const token = process.env['BOT_TOKEN'];
if (!token) throw new Error('BOT_TOKEN is required');

const bot = new Bot(token);

registerCommands(bot);
registerHandlers(bot);

bot.catch((err) => {
  console.error('[bot] Error:', err.message);
});

bot.start({ onStart: () => console.log('[bot] SalesCoach bot started') });

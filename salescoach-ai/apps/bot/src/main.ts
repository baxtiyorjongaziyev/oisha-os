import 'dotenv/config';
import { Bot, session } from 'grammy';
import { registerCommands } from './commands';
import { registerHandlers } from './handlers';

const token = process.env.BOT_TOKEN;
if (!token) throw new Error('BOT_TOKEN is required');

const bot = new Bot(token);
bot.use(session({ initial: () => ({}) }));

registerCommands(bot);
registerHandlers(bot);

bot.catch((err) => {
  console.error('[bot] Error:', err.message);
});

bot.start({ onStart: () => console.log('[bot] SalesCoach bot started') });

import { Bot, Context } from 'grammy';
import { handleAudio } from './audio.handler.js';

export function registerHandlers(bot: Bot<Context>) {
  bot.on('message:audio', (ctx) => handleAudio(ctx));
  bot.on('message:voice', (ctx) => handleAudio(ctx));
  bot.on('message:document', async (ctx) => {
    const doc = ctx.message.document;
    if (doc?.mime_type?.startsWith('audio/')) {
      await handleAudio(ctx);
    } else {
      await ctx.reply('Please send an audio file for analysis.');
    }
  });
}

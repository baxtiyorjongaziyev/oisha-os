import { Bot } from 'grammy';
import { handleAudio } from './audio.handler';

export function registerHandlers(bot: Bot) {
  bot.on('message:audio', handleAudio);
  bot.on('message:voice', handleAudio);
  bot.on('message:document', async (ctx) => {
    const doc = ctx.message.document;
    if (doc?.mime_type?.startsWith('audio/')) {
      return handleAudio(ctx as any);
    }
    await ctx.reply('Please send an audio file for analysis.');
  });
}

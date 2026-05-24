import type { Context, Api } from 'grammy';

const FLUSH_CHARS = 40;
const FLUSH_INTERVAL_MS = 900;
const MAX_LEN = 4000;
const CURSOR = ' ▌';

/**
 * Sends a placeholder message then edits it progressively as an async
 * iterator yields text chunks — giving a ChatGPT-style streaming effect.
 *
 * Usage:
 *   const streamer = new TelegramStreamer(ctx);
 *   await streamer.start('⌛');
 *   for await (const chunk of llmStream) {
 *     await streamer.push(chunk);
 *   }
 *   await streamer.finish();
 */
export class TelegramStreamer {
  private chatId: number;
  private messageId: number | null = null;
  private api: Api;
  private fullText = '';
  private buffer = '';
  private lastFlush = 0;

  constructor(private ctx: Context) {
    this.chatId = ctx.chat!.id;
    this.api = ctx.api;
  }

  async start(placeholder = '⌛'): Promise<void> {
    const msg = await this.ctx.reply(placeholder);
    this.messageId = msg.message_id;
    this.lastFlush = Date.now();
  }

  async push(chunk: string): Promise<void> {
    if (!chunk) return;
    this.fullText += chunk;
    this.buffer += chunk;

    const now = Date.now();
    const shouldFlush =
      this.buffer.length >= FLUSH_CHARS ||
      now - this.lastFlush >= FLUSH_INTERVAL_MS;

    if (shouldFlush) await this._flush(true);
  }

  async finish(): Promise<string> {
    await this._flush(false);
    return this.fullText;
  }

  private async _flush(withCursor: boolean): Promise<void> {
    if (!this.messageId) return;
    const text = this.fullText.slice(-MAX_LEN) + (withCursor ? CURSOR : '');
    try {
      await this.api.editMessageText(this.chatId, this.messageId, text);
    } catch {
      // Message not modified or too fast — ignore
    }
    this.buffer = '';
    this.lastFlush = Date.now();
  }
}

/**
 * Convenience: stream a static string word-by-word (demo / fallback).
 */
export async function streamText(ctx: Context, text: string): Promise<void> {
  const streamer = new TelegramStreamer(ctx);
  await streamer.start('⌛');
  const words = text.split(' ');
  for (const word of words) {
    await streamer.push(word + ' ');
    await new Promise((r) => setTimeout(r, 30));
  }
  await streamer.finish();
}

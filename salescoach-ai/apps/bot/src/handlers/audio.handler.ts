import { Context } from 'grammy';

interface UploadInitResponse {
  callId: string;
  uploadUrl: string;
  audioKey: string;
}

export async function handleAudio(ctx: Context) {
  const msg = ctx.message;
  const fileId = msg?.audio?.file_id ?? msg?.voice?.file_id ?? msg?.document?.file_id;
  if (!fileId) {
    await ctx.reply('Could not read audio file.');
    return;
  }

  const statusMsg = await ctx.reply('Processing your call recording...');

  try {
    const apiUrl = process.env['API_URL'] ?? 'http://localhost:4000/v1';
    const apiToken = process.env['BOT_API_TOKEN'];
    if (!apiToken) {
      await ctx.reply('Bot not configured for API access.');
      return;
    }

    const fileInfo = await ctx.api.getFile(fileId);
    const telegramUrl = `https://api.telegram.org/file/bot${process.env['BOT_TOKEN']}/${fileInfo.file_path}`;

    const initRes = await fetch(`${apiUrl}/calls`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${apiToken}` },
      body: JSON.stringify({
        customerName: `Telegram: ${ctx.from?.first_name ?? 'Unknown'}`,
        direction: 'INBOUND',
        ext: 'ogg',
        contentType: 'audio/ogg',
      }),
    });

    if (!initRes.ok) throw new Error('Failed to initiate upload');
    const { callId, uploadUrl } = (await initRes.json()) as UploadInitResponse;

    const audioRes = await fetch(telegramUrl);
    if (!audioRes.ok) throw new Error('Failed to download from Telegram');
    const audioBuffer = await audioRes.arrayBuffer();

    await fetch(uploadUrl, {
      method: 'PUT',
      body: audioBuffer,
      headers: { 'Content-Type': 'audio/ogg' },
    });

    await fetch(`${apiUrl}/calls/${callId}/confirm`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${apiToken}` },
    });

    await ctx.api.editMessageText(
      ctx.chat!.id,
      statusMsg.message_id,
      `Call uploaded! Analysis in progress.\n\nCall ID: \`${callId}\`\n` +
      `You'll receive the report once transcription and scoring complete.`,
      { parse_mode: 'Markdown' },
    );
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Unknown error';
    await ctx.api.editMessageText(
      ctx.chat!.id,
      statusMsg.message_id,
      `Failed to process: ${message}`,
    );
  }
}

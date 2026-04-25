import { Context } from 'grammy';

export async function handleAudio(ctx: Context) {
  const msg = ctx.message;
  const fileId = msg?.audio?.file_id ?? msg?.voice?.file_id ?? msg?.document?.file_id;
  if (!fileId) return ctx.reply('Could not read audio file.');

  const statusMsg = await ctx.reply('Processing your call recording...');

  try {
    const apiUrl = process.env.API_URL ?? 'http://localhost:4000/v1';
    const apiToken = process.env.BOT_API_TOKEN;
    if (!apiToken) return ctx.reply('Bot not configured for API access.');

    // Get Telegram file URL
    const fileInfo = await ctx.api.getFile(fileId);
    const telegramUrl = `https://api.telegram.org/file/bot${process.env.BOT_TOKEN}/${fileInfo.file_path}`;

    // Initiate upload
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
    const { callId, uploadUrl } = await initRes.json();

    // Fetch from Telegram and upload to S3
    const audioRes = await fetch(telegramUrl);
    if (!audioRes.ok) throw new Error('Failed to download from Telegram');
    const audioBuffer = await audioRes.arrayBuffer();

    await fetch(uploadUrl, {
      method: 'PUT',
      body: audioBuffer,
      headers: { 'Content-Type': 'audio/ogg' },
    });

    // Confirm and enqueue
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
  } catch (err: any) {
    await ctx.api.editMessageText(
      ctx.chat!.id,
      statusMsg.message_id,
      `Failed to process: ${err.message}`,
    );
  }
}

import { prisma } from './prisma.js';

export interface CoachingCard {
  callId: string;
  managerId: string;
  overallScore: number;
  grade: 'A' | 'B' | 'C' | 'D';
  headline: string;
  goodPoints: string[];
  improvementPoints: string[];
  recommendedPhrase: string;
  nextStepCommitments: { manager: string[]; customer: string[] };
  riskFlags: string[];
  telegramMessage: string;
}

/**
 * CoachingDeliveryAgent — generates and delivers coaching feedback to managers
 * after a call is scored. Sends a Telegram message via Bot API.
 *
 * Invoked by ScoringWorker after scorecard.upsert().
 */
export class CoachingService {
  private botToken = process.env['BOT_TOKEN'] ?? '';
  private telegramApi = 'https://api.telegram.org';

  async deliver(callId: string): Promise<CoachingCard | null> {
    const [call, scorecard] = await Promise.all([
      prisma.call.findUnique({
        where: { id: callId },
        include: { manager: true },
      }),
      prisma.scorecard.findUnique({ where: { callId } }),
    ]);

    if (!call || !scorecard) return null;

    const card = this._buildCard(callId, call, scorecard);

    // telegramId not in User model yet — log coaching card, send when field is available
    const telegramId: string | undefined = (call.manager as any).telegramId;
    if (this.botToken && telegramId) {
      await this._sendTelegram(telegramId, card.telegramMessage);
    } else {
      console.log(`[coaching] Card for call ${callId} (no telegramId):`, card.headline);
    }

    return card;
  }

  private _buildCard(callId: string, call: any, scorecard: any): CoachingCard {
    const score: number = scorecard.overallScore ?? 0;
    const grade = this._grade(score);
    const nextStep = (scorecard.nextStepCommitments as any) ?? {
      manager: [],
      customer: [],
    };
    const voiceAnalytics = (scorecard.voiceAnalytics as any) ?? {};

    const headline = this._headline(grade, call.customerName ?? 'Mijoz');

    const telegramMessage = this._formatTelegram({
      headline,
      grade,
      score,
      customerName: call.customerName ?? "Noma'lum",
      durationSec: call.durationSec ?? 0,
      managerTalkRatio: voiceAnalytics.managerTalkRatio ?? 0,
      wpm: voiceAnalytics.wpm ?? 0,
      summary: scorecard.summary ?? '',
      goodPoints: scorecard.goodPoints ?? [],
      improvementPoints: scorecard.improvementPoints ?? [],
      recommendedPhrase: scorecard.recommendedPhrase ?? '',
      nextStep,
      riskFlags: scorecard.riskFlags ?? [],
    });

    return {
      callId,
      managerId: call.managerId,
      overallScore: score,
      grade,
      headline,
      goodPoints: scorecard.goodPoints ?? [],
      improvementPoints: scorecard.improvementPoints ?? [],
      recommendedPhrase: scorecard.recommendedPhrase ?? '',
      nextStepCommitments: nextStep,
      riskFlags: scorecard.riskFlags ?? [],
      telegramMessage,
    };
  }

  private _grade(score: number): 'A' | 'B' | 'C' | 'D' {
    if (score >= 85) return 'A';
    if (score >= 70) return 'B';
    if (score >= 55) return 'C';
    return 'D';
  }

  private _headline(
    grade: 'A' | 'B' | 'C' | 'D',
    customerName: string,
  ): string {
    const map: Record<string, string> = {
      A: `Zo'r! ${customerName} bilan suhbat muvaffaqiyatli o'tdi`,
      B: `Yaxshi suhbat, bir-ikki nuqta yaxshilanishi mumkin`,
      C: `${customerName} bilan suhbatda rivojlanish imkoniyatlari ko'p`,
      D: `Jiddiy ko'rib chiqish kerak — asosiy texnikalar etishmayapti`,
    };
    return map[grade] ?? `Baho: ${grade}`;
  }

  private _formatTelegram(data: {
    headline: string;
    grade: string;
    score: number;
    customerName: string;
    durationSec: number;
    managerTalkRatio: number;
    wpm: number;
    summary: string;
    goodPoints: string[];
    improvementPoints: string[];
    recommendedPhrase: string;
    nextStep: { manager: string[]; customer: string[] };
    riskFlags: string[];
  }): string {
    const gradeEmoji: Record<string, string> = {
      A: '🏆',
      B: '✅',
      C: '⚠️',
      D: '🔴',
    };
    const mins = Math.floor(data.durationSec / 60);
    const secs = data.durationSec % 60;

    let msg = `${gradeEmoji[data.grade] ?? '📊'} *Coaching Card — Baho: ${data.grade} (${data.score}/100)*\n`;
    msg += `_${data.headline}_\n\n`;

    msg += `👤 Mijoz: ${data.customerName}\n`;
    msg += `⏱ Davomiylik: ${mins}m ${secs}s\n`;
    msg += `🗣 Manager gapirish ulushi: ${Math.round(data.managerTalkRatio * 100)}%\n`;
    msg += `⚡ So'z tezligi: ${data.wpm} so'z/daqiqa\n\n`;

    if (data.summary) {
      msg += `📝 *Xulosa*\n${data.summary}\n\n`;
    }

    if (data.goodPoints.length) {
      msg += `✅ *Yaxshi tomonlar*\n`;
      data.goodPoints.forEach((p) => (msg += `• ${p}\n`));
      msg += '\n';
    }

    if (data.improvementPoints.length) {
      msg += `📈 *Rivojlantirish kerak*\n`;
      data.improvementPoints.forEach((p) => (msg += `• ${p}\n`));
      msg += '\n';
    }

    if (data.recommendedPhrase) {
      msg += `💬 *Tavsiya etilgan ibora*\n"${data.recommendedPhrase}"\n\n`;
    }

    if (data.nextStep.manager.length) {
      msg += `🎯 *Sizning keyingi qadamlar*\n`;
      data.nextStep.manager.forEach((s) => (msg += `• ${s}\n`));
      msg += '\n';
    }

    if (data.riskFlags.length) {
      msg += `⚠️ *Risk signallari*\n`;
      data.riskFlags.forEach((f) => (msg += `• ${f}\n`));
    }

    return msg;
  }

  private async _sendTelegram(chatId: string, text: string): Promise<void> {
    if (!this.botToken) return;

    const url = `${this.telegramApi}/bot${this.botToken}/sendMessage`;
    const body = JSON.stringify({
      chat_id: chatId,
      text,
      parse_mode: 'Markdown',
    });

    await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body,
    }).catch((err) => {
      console.error('[coaching] Telegram send failed:', err.message);
    });
  }
}

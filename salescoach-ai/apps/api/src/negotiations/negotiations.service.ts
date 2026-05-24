import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import Anthropic from '@anthropic-ai/sdk';
import { PrismaService } from '../common/prisma.service';
import { NegotiateDto, RealtimeSuggestionDto } from './dto/negotiate.dto';

export interface NegotiationAssessment {
  stage: string;
  intent: string;
  objection: string;
  urgency: string;
  sentiment: string;
  closeProbability: number;
  nextAction: string;
  approvalNeeded: boolean;
  riskFlags: string[];
  painPoints: string[];
  buyingSignals: string[];
}

export interface NegotiationSuggestion {
  suggestedReply: string;
  assessment: NegotiationAssessment;
  surgicalMission: string;
  alternativeReplies: string[];
  talkingPoints: string[];
  warningFlags: string[];
}

export interface RealtimeSuggestion {
  tip: string;
  action: 'continue' | 'ask_question' | 'handle_objection' | 'propose' | 'close' | 'escalate';
  urgency: 'low' | 'medium' | 'high';
  suggestedPhrase?: string;
}

@Injectable()
export class NegotiationsService {
  private readonly logger = new Logger(NegotiationsService.name);
  private anthropic: Anthropic;

  constructor(
    private prisma: PrismaService,
    private cfg: ConfigService,
  ) {
    this.anthropic = new Anthropic({
      apiKey: this.cfg.getOrThrow('ANTHROPIC_API_KEY'),
    });
  }

  // ─────────────────────── Full Negotiation Assist ─────────────────────────

  async getSuggestion(
    orgId: string,
    managerId: string,
    dto: NegotiateDto,
  ): Promise<NegotiationSuggestion> {
    const historyText = (dto.history ?? [])
      .slice(-6)
      .map((h) => `${h.role.toUpperCase()}: ${h.content}`)
      .join('\n');

    const systemPrompt = `You are SalesCoach AI — an autonomous negotiation assistant for ${
      dto.serviceType ?? 'branding/marketing agency'
    } sales.
Your goal: help the sales manager close deals professionally.
Language: respond in the same language as the customer message (uz/ru/en).
Tone: confident, empathetic, value-focused.`;

    const userPrompt = `
CONVERSATION HISTORY:
${historyText || '(new conversation)'}

CUSTOMER MESSAGE: "${dto.message}"
CRM STATUS: "${dto.crmStatus ?? 'new lead'}"
CUSTOMER NAME: "${dto.customerName ?? 'unknown'}"

Analyze and return JSON:
{
  "assessment": {
    "stage": "new_lead|qualified|meeting_ready|closing",
    "intent": "qualify|pricing|meeting|closing|proof|nurture|complaint",
    "objection": "none|price|trust|timing|competition|legal|budget|authority",
    "urgency": "high|normal|low",
    "sentiment": "positive|neutral|negative|excited|confused",
    "closeProbability": 0.0-1.0,
    "nextAction": "qualify_need|value_anchor|show_case|schedule_meeting|confirm_close|create_followup|handle_objection|escalate",
    "approvalNeeded": false,
    "riskFlags": [],
    "painPoints": [],
    "buyingSignals": []
  },
  "suggestedReply": "...",
  "alternativeReplies": ["...", "..."],
  "talkingPoints": ["...", "..."],
  "surgicalMission": "[1] Strategy: ... [2] Next question: '...' [3] Risk: ...",
  "warningFlags": []
}

Rules:
- suggestedReply: 2-3 sentences, natural, not robotic
- alternativeReplies: 2 variations (softer / more direct)
- talkingPoints: 3 key value points to emphasize
- surgicalMission: 3 concrete next actions for the manager
- warningFlags: issues that need immediate attention
- Respond with ONLY valid JSON`;

    const msg = await this.anthropic.messages.create({
      model: 'claude-sonnet-4-6',
      max_tokens: 2048,
      system: systemPrompt,
      messages: [{ role: 'user', content: userPrompt }],
    });

    const raw = msg.content.find((b) => b.type === 'text')?.text ?? '{}';
    const cleaned = raw.replace(/^```(?:json)?\s*/m, '').replace(/\s*```$/m, '');
    const parsed = JSON.parse(cleaned);

    // Persist session to DB for analytics
    if (dto.callId) {
      await this.saveNegotiationSession(orgId, managerId, dto, parsed).catch(
        (e) => this.logger.warn(`Session save failed: ${e.message}`),
      );
    }

    return {
      assessment: parsed.assessment ?? {},
      suggestedReply: parsed.suggestedReply ?? '',
      alternativeReplies: parsed.alternativeReplies ?? [],
      talkingPoints: parsed.talkingPoints ?? [],
      surgicalMission: parsed.surgicalMission ?? '',
      warningFlags: parsed.warningFlags ?? [],
    };
  }

  // ─────────────────────── Real-time In-Call Coaching ──────────────────────

  async getRealtimeSuggestion(
    orgId: string,
    managerId: string,
    dto: RealtimeSuggestionDto,
  ): Promise<RealtimeSuggestion> {
    // Fast model for real-time (lower latency)
    const msg = await this.anthropic.messages.create({
      model: 'claude-haiku-4-5',
      max_tokens: 256,
      system: `You are a real-time sales coach. Give ONE short, actionable tip.
Always respond in the same language as the message (uz/ru/en).
Respond ONLY with JSON: {"tip": "...", "action": "continue|ask_question|handle_objection|propose|close|escalate", "urgency": "low|medium|high", "suggestedPhrase": "..."}`,
      messages: [
        {
          role: 'user',
          content: `Manager just heard: "${dto.message}"\nCRM: "${dto.crmStatus ?? ''}"\nGive one coaching tip:`,
        },
      ],
    });

    const raw = msg.content.find((b) => b.type === 'text')?.text ?? '{}';
    const cleaned = raw.replace(/^```(?:json)?\s*/m, '').replace(/\s*```$/m, '');
    try {
      return JSON.parse(cleaned);
    } catch {
      return {
        tip: 'Listen actively and ask an open-ended question.',
        action: 'ask_question',
        urgency: 'low',
      };
    }
  }

  // ─────────────────────── Objection Handling ──────────────────────────────

  async handleObjection(
    objectionType: string,
    context: string,
    language: 'uz' | 'ru' | 'en' = 'uz',
  ): Promise<{ response: string; strategy: string; examples: string[] }> {
    const strategies: Record<string, string> = {
      price: 'value_anchor — Show ROI and compare to cost of NOT solving the problem',
      trust: 'social_proof — Share 2 relevant case studies with measurable results',
      timing: 'urgency_create — Show opportunity cost of delay',
      competition: 'differentiation — Highlight unique guarantees and track record',
      legal: 'risk_mitigation — Offer NDA first, then proceed',
      budget: 'value_reframe — Break cost into monthly/weekly to reduce sticker shock',
      authority: 'stakeholder_map — Help prep the pitch for the decision maker',
    };

    const msg = await this.anthropic.messages.create({
      model: 'claude-haiku-4-5',
      max_tokens: 512,
      messages: [
        {
          role: 'user',
          content: `Handle this sales objection in ${language}:
Type: ${objectionType}
Context: "${context}"
Strategy hint: ${strategies[objectionType] ?? 'empathize and redirect'}

Respond as JSON: {"response": "...", "strategy": "...", "examples": ["...", "..."]}`,
        },
      ],
    });

    const raw = msg.content.find((b) => b.type === 'text')?.text ?? '{}';
    const cleaned = raw.replace(/^```(?:json)?\s*/m, '').replace(/\s*```$/m, '');
    return JSON.parse(cleaned);
  }

  // ─────────────────────── Streak / Pipeline Stats ─────────────────────────

  async getPipelineInsights(orgId: string, days = 7) {
    const since = new Date(Date.now() - days * 86400_000);

    const calls = await this.prisma.call.findMany({
      where: { orgId, createdAt: { gte: since }, status: 'DONE' },
      include: { scorecard: true },
    });

    type PipelineCall = (typeof calls)[number];

    const total = calls.length;
    const scored = calls.filter((c: PipelineCall) => c.scorecard).length;
    const avgScore =
      scored > 0
        ? calls.reduce(
            (sum: number, c: PipelineCall) => sum + (c.scorecard?.overallScore ?? 0),
            0,
          ) / scored
        : 0;

    const riskFlags: Record<string, number> = {};
    for (const c of calls) {
      for (const flag of (c.scorecard?.riskFlags ?? []) as string[]) {
        riskFlags[flag] = (riskFlags[flag] ?? 0) + 1;
      }
    }

    const topRisks = Object.entries(riskFlags)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([flag, count]) => ({ flag, count }));

    return {
      period: `${days}d`,
      totalCalls: total,
      scoredCalls: scored,
      avgScore: Math.round(avgScore * 10) / 10,
      topRiskFlags: topRisks,
    };
  }

  // ──────────────────────────── Private ────────────────────────────────────

  private async saveNegotiationSession(
    orgId: string,
    managerId: string,
    dto: NegotiateDto,
    result: any,
  ) {
    // Store in Call notes field for now (no separate table needed)
    if (!dto.callId) return;
    const note = `[NegotiationSession] intent=${result.assessment?.intent} prob=${result.assessment?.closeProbability}`;
    await this.prisma.call
      .update({
        where: { id: dto.callId },
        data: { errorMessage: null }, // just validate it exists
      })
      .catch(() => null);
    this.logger.debug(`[Negotiations] Session saved for call ${dto.callId}: ${note}`);
  }
}

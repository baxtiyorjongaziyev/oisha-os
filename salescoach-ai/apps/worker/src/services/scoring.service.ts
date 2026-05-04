import Anthropic from '@anthropic-ai/sdk';
import { LLMScorecardOutput, LLMScorecardOutputSchema } from '@salescoach/shared-types';

const SYSTEM_PROMPT = `You are SalesCoach AI — an expert sales call analyst specializing in
Central Asian markets (Uzbekistan, Russia, CIS). You understand Uzbek and Russian sales culture:
relationship-building (ishonch/doverie), face-saving, authority-based decisions, and price sensitivity.

Analyze the provided call transcript and return a detailed JSON scorecard.
All scores 0-100. Be specific, actionable, and culturally aware.
Respond ONLY with valid JSON — no markdown, no preamble, no explanation.`;

const buildUserPrompt = (
  transcript: string,
  language: 'uz' | 'ru' | 'en',
  durationSec?: number,
) => {
  const langHint = {
    uz: "Uzbek market — relationship-first culture, price sensitivity common, authority matters",
    ru: "Russian-speaking market — formal tone preferred, written confirmation important",
    en: "International market — direct communication, ROI-focused",
  }[language];

  return `Language: ${language.toUpperCase()} | Market context: ${langHint}
Duration: ${durationSec ? `${Math.round(durationSec / 60)}min` : 'unknown'}

TRANSCRIPT:
${transcript}

Return JSON exactly matching this schema:
{
  "overallScore": number (0-100),
  "stageScores": [
    { "stage": "opening", "score": number, "reasoning": "..." },
    { "stage": "need_discovery", "score": number, "reasoning": "..." },
    { "stage": "value_presentation", "score": number, "reasoning": "..." },
    { "stage": "objection_handling", "score": number, "reasoning": "..." },
    { "stage": "closing", "score": number, "reasoning": "..." },
    { "stage": "rapport_building", "score": number, "reasoning": "..." }
  ],
  "voiceAnalytics": {
    "tone": "confident" | "hesitant" | "neutral" | "aggressive" | "empathetic",
    "energy": "high" | "medium" | "low",
    "listenRatio": number (0-1, estimated customer vs manager talk)
  },
  "summary": "2-3 sentence summary of what happened in the call",
  "goodPoints": [
    "Specific thing manager did well with example from transcript"
  ],
  "improvementPoints": [
    "Specific thing to improve with exact moment from transcript"
  ],
  "recommendedPhrase": "One exact phrase the manager could use next time for the key missed opportunity",
  "nextStepCommitments": {
    "manager": ["Specific action manager committed to"],
    "customer": ["Specific action customer committed to (if any)"]
  },
  "riskFlags": [
    "price_objection_unhandled" | "competitor_mentioned" | "no_next_step" | "negative_sentiment" |
    "authority_issue" | "call_too_short" | "rushed_close" | "rapport_missing" | "value_not_communicated"
  ],
  "leadQualityScore": number (0-100, how qualified is this lead based on the conversation),
  "predictedOutcome": "sale" | "follow_up" | "lost" | "nurture",
  "objections": [
    { "type": "price|trust|timing|competition|legal|budget|authority", "handled": boolean, "quality": "excellent|good|poor" }
  ]
}`;
};

export class ScoringService {
  private client: Anthropic;

  constructor() {
    this.client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
  }

  async score(
    transcript: string,
    language: 'uz' | 'ru' | 'en',
    durationSec?: number,
  ): Promise<LLMScorecardOutput> {
    const message = await this.client.messages.create({
      model: 'claude-sonnet-4-6',
      max_tokens: 4096,
      system: SYSTEM_PROMPT,
      messages: [
        {
          role: 'user',
          content: buildUserPrompt(transcript, language, durationSec),
        },
      ],
    });

    const text = message.content.find((b) => b.type === 'text')?.text ?? '';
    const clean = text.replace(/^```(?:json)?\s*/m, '').replace(/\s*```$/m, '');
    const parsed = JSON.parse(clean);
    return LLMScorecardOutputSchema.parse(parsed);
  }
}

import Anthropic from '@anthropic-ai/sdk';
import { LLMScorecardOutput, LLMScorecardOutputSchema } from '@salescoach/shared-types';

const SYSTEM_PROMPT = `You are SalesCoach AI, an expert sales call analyst.
Analyze the provided call transcript and return a JSON scorecard.
All scores are 0-100. Be specific and actionable in reasoning.
Respond ONLY with valid JSON matching the schema — no markdown, no preamble.`;

const buildUserPrompt = (transcript: string, language: 'uz' | 'ru' | 'en') => `
Language: ${language}
Transcript:
${transcript}

Return JSON with:
{
  "overallScore": number,
  "stageScores": [{ "stage": string, "score": number, "reasoning": string }],
  "voiceAnalytics": { "tone": "confident"|"hesitant"|"neutral", "energy": "high"|"medium"|"low" },
  "summary": string,
  "goodPoints": string[],
  "improvementPoints": string[],
  "recommendedPhrase": string,
  "nextStepCommitments": { "manager": string[], "customer": string[] },
  "riskFlags": string[],
  "leadQualityScore": number
}`;

export class ScoringService {
  private client: Anthropic;

  constructor() {
    this.client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
  }

  async score(transcript: string, language: 'uz' | 'ru' | 'en'): Promise<LLMScorecardOutput> {
    const message = await this.client.messages.create({
      model: 'claude-sonnet-4-6',
      max_tokens: 4096,
      system: SYSTEM_PROMPT,
      messages: [{ role: 'user', content: buildUserPrompt(transcript, language) }],
    });

    const text = message.content.find((b) => b.type === 'text')?.text ?? '';
    const parsed = JSON.parse(text);
    return LLMScorecardOutputSchema.parse(parsed);
  }
}

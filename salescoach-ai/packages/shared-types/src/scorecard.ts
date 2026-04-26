import { z } from 'zod';

export const StageScoreSchema = z.object({
  stage: z.string(),
  score: z.number().min(0).max(100),
  reasoning: z.string(),
});

export const VoiceAnalyticsSchema = z.object({
  managerTalkRatio: z.number().min(0).max(1),
  customerTalkRatio: z.number().min(0).max(1),
  wpm: z.number(),
  tone: z.enum(['confident', 'hesitant', 'neutral']),
  energy: z.enum(['high', 'medium', 'low']),
});

export const ScorecardSchema = z.object({
  id: z.string().uuid(),
  callId: z.string().uuid(),
  overallScore: z.number().min(0).max(100),
  stageScores: z.array(StageScoreSchema),
  voiceAnalytics: VoiceAnalyticsSchema,
  summary: z.string(),
  goodPoints: z.array(z.string()),
  improvementPoints: z.array(z.string()),
  recommendedPhrase: z.string(),
  nextStepCommitments: z.object({
    manager: z.array(z.string()),
    customer: z.array(z.string()),
  }),
  riskFlags: z.array(z.string()),
  leadQualityScore: z.number().min(0).max(100),
});

export type StageScore = z.infer<typeof StageScoreSchema>;
export type VoiceAnalytics = z.infer<typeof VoiceAnalyticsSchema>;
export type Scorecard = z.infer<typeof ScorecardSchema>;

// LLM output schema — what we expect the LLM to return
export const LLMScorecardOutputSchema = ScorecardSchema.omit({
  id: true,
  callId: true,
  voiceAnalytics: true,
}).extend({
  voiceAnalytics: VoiceAnalyticsSchema.omit({
    managerTalkRatio: true,
    customerTalkRatio: true,
    wpm: true,
  }),
});

export type LLMScorecardOutput = z.infer<typeof LLMScorecardOutputSchema>;

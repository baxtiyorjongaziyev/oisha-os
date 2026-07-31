import {
  normalizeConversationAnalysis,
  type ConversationAnalysis,
} from './conversation-analysis.types';

const zeroScores = {
  opening: 0,
  needsDiscovery: 0,
  solutionFit: 0,
  valueExplanation: 0,
  objectionHandling: 0,
  nextStep: 0,
  responseDiscipline: 0,
};

describe('normalizeConversationAnalysis', () => {
  it('recalculates overall score from the weighted category scores', () => {
    const result = normalizeConversationAnalysis(
      {
        overallScore: 99,
        scores: {
          opening: 8,
          needsDiscovery: 14,
          solutionFit: 10,
          valueExplanation: 9,
          objectionHandling: 7,
          nextStep: 10,
          responseDiscipline: 6,
        },
        confidence: 0.91,
      },
      new Set([1001, 1002]),
    );

    expect(result.overallScore).toBe(64);
  });

  it('clamps category scores and confidence to their allowed ranges', () => {
    const result = normalizeConversationAnalysis(
      {
        scores: {
          opening: 99,
          needsDiscovery: -4,
          solutionFit: 16,
          valueExplanation: 15,
          objectionHandling: 18,
          nextStep: 20,
          responseDiscipline: 12,
        },
        confidence: 3,
      },
      new Set([1001]),
    );

    expect(result.scores).toEqual({
      opening: 10,
      needsDiscovery: 0,
      solutionFit: 15,
      valueExplanation: 15,
      objectionHandling: 15,
      nextStep: 15,
      responseDiscipline: 10,
    });
    expect(result.overallScore).toBe(80);
    expect(result.confidence).toBe(1);
  });

  it('drops hallucinated evidence message ids from the analysis and tasks', () => {
    const result = normalizeConversationAnalysis(
      {
        scores: zeroScores,
        evidenceMessageIds: [1001, 9999],
        recommendedTasks: [
          {
            type: 'follow_up',
            reason: 'Mijoz keyinroq javob berishini aytdi',
            evidenceMessageIds: [1002, 8888],
          },
        ],
        confidence: 0.8,
      },
      new Set([1001, 1002]),
    );

    expect(result.evidenceMessageIds).toEqual([1001]);
    expect(result.recommendedTasks[0].evidenceMessageIds).toEqual([1002]);
  });

  it('returns safe defaults for malformed optional fields', () => {
    const result: ConversationAnalysis = normalizeConversationAnalysis(
      {
        scores: zeroScores,
        clientIntent: 'invented',
        dealRisk: 'extreme',
        strengths: 'not-an-array',
        confidence: 'invalid',
      },
      new Set<number>(),
    );

    expect(result.clientIntent).toBe('cold');
    expect(result.dealRisk).toBe('medium');
    expect(result.strengths).toEqual([]);
    expect(result.confidence).toBe(0);
  });
});

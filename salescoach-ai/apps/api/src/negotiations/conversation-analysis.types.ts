export type ClientIntent = 'cold' | 'warm' | 'hot';
export type DealRisk = 'low' | 'medium' | 'high';
export type RecommendedTaskType =
  | 'reply_customer'
  | 'schedule_meeting'
  | 'send_proposal'
  | 'follow_up'
  | 'send_material'
  | 'manager_review';

export interface ConversationScores {
  opening: number;
  needsDiscovery: number;
  solutionFit: number;
  valueExplanation: number;
  objectionHandling: number;
  nextStep: number;
  responseDiscipline: number;
}

export interface RecommendedConversationTask {
  type: RecommendedTaskType;
  reason: string;
  evidenceMessageIds: number[];
}

export interface ConversationAnalysis {
  overallScore: number;
  scores: ConversationScores;
  strengths: string[];
  mistakes: string[];
  missedQuestions: string[];
  clientIntent: ClientIntent;
  objections: string[];
  dealRisk: DealRisk;
  nextBestAction: string;
  recommendedReply: string;
  recommendedTasks: RecommendedConversationTask[];
  confidence: number;
  evidenceMessageIds: number[];
}

export const SCORE_LIMITS: Readonly<ConversationScores> = {
  opening: 10,
  needsDiscovery: 20,
  solutionFit: 15,
  valueExplanation: 15,
  objectionHandling: 15,
  nextStep: 15,
  responseDiscipline: 10,
};

const TASK_TYPES = new Set<RecommendedTaskType>([
  'reply_customer',
  'schedule_meeting',
  'send_proposal',
  'follow_up',
  'send_material',
  'manager_review',
]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function toFiniteNumber(value: unknown, fallback = 0): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback;
}

function clamp(value: unknown, minimum: number, maximum: number): number {
  const numberValue = toFiniteNumber(value, minimum);
  return Math.min(maximum, Math.max(minimum, numberValue));
}

function stringValue(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

function stringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value
    .filter((item): item is string => typeof item === 'string')
    .map((item) => item.trim())
    .filter(Boolean);
}

function evidenceIds(value: unknown, allowedMessageIds: Set<number>): number[] {
  if (!Array.isArray(value)) return [];
  return Array.from(
    new Set(
      value.filter(
        (item): item is number =>
          typeof item === 'number' &&
          Number.isInteger(item) &&
          allowedMessageIds.has(item),
      ),
    ),
  );
}

function clientIntent(value: unknown): ClientIntent {
  return value === 'warm' || value === 'hot' ? value : 'cold';
}

function dealRisk(value: unknown): DealRisk {
  return value === 'low' || value === 'high' ? value : 'medium';
}

function recommendedTasks(
  value: unknown,
  allowedMessageIds: Set<number>,
): RecommendedConversationTask[] {
  if (!Array.isArray(value)) return [];

  const tasks: RecommendedConversationTask[] = [];
  for (const item of value) {
    if (!isRecord(item)) continue;
    const type = item.type;
    const reason = stringValue(item.reason);
    if (typeof type !== 'string' || !TASK_TYPES.has(type as RecommendedTaskType) || !reason) {
      continue;
    }
    tasks.push({
      type: type as RecommendedTaskType,
      reason,
      evidenceMessageIds: evidenceIds(item.evidenceMessageIds, allowedMessageIds),
    });
  }
  return tasks;
}

export function normalizeConversationAnalysis(
  raw: unknown,
  allowedMessageIds: Set<number>,
): ConversationAnalysis {
  const data = isRecord(raw) ? raw : {};
  const rawScores = isRecord(data.scores) ? data.scores : {};

  const scores: ConversationScores = {
    opening: clamp(rawScores.opening, 0, SCORE_LIMITS.opening),
    needsDiscovery: clamp(
      rawScores.needsDiscovery,
      0,
      SCORE_LIMITS.needsDiscovery,
    ),
    solutionFit: clamp(rawScores.solutionFit, 0, SCORE_LIMITS.solutionFit),
    valueExplanation: clamp(
      rawScores.valueExplanation,
      0,
      SCORE_LIMITS.valueExplanation,
    ),
    objectionHandling: clamp(
      rawScores.objectionHandling,
      0,
      SCORE_LIMITS.objectionHandling,
    ),
    nextStep: clamp(rawScores.nextStep, 0, SCORE_LIMITS.nextStep),
    responseDiscipline: clamp(
      rawScores.responseDiscipline,
      0,
      SCORE_LIMITS.responseDiscipline,
    ),
  };

  const overallScore = Object.values(scores).reduce((sum, score) => sum + score, 0);

  return {
    overallScore,
    scores,
    strengths: stringArray(data.strengths),
    mistakes: stringArray(data.mistakes),
    missedQuestions: stringArray(data.missedQuestions),
    clientIntent: clientIntent(data.clientIntent),
    objections: stringArray(data.objections),
    dealRisk: dealRisk(data.dealRisk),
    nextBestAction: stringValue(data.nextBestAction),
    recommendedReply: stringValue(data.recommendedReply),
    recommendedTasks: recommendedTasks(data.recommendedTasks, allowedMessageIds),
    confidence: clamp(data.confidence, 0, 1),
    evidenceMessageIds: evidenceIds(data.evidenceMessageIds, allowedMessageIds),
  };
}

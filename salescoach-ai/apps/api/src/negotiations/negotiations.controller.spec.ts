import { plainToInstance } from 'class-transformer';
import { validate } from 'class-validator';
import { NegotiationsController } from './negotiations.controller';
import {
  AnalyzeConversationDto,
  ConversationRole,
} from './dto/analyze-conversation.dto';

const validAnalysis = {
  overallScore: 64,
  scores: {
    opening: 8,
    needsDiscovery: 14,
    solutionFit: 10,
    valueExplanation: 9,
    objectionHandling: 7,
    nextStep: 10,
    responseDiscipline: 6,
  },
  strengths: ['Mijozni tingladi'],
  mistakes: [],
  missedQuestions: [],
  clientIntent: 'warm' as const,
  objections: ['price'],
  dealRisk: 'medium' as const,
  nextBestAction: 'Uchrashuv vaqtini aniqlash',
  recommendedReply: 'Sizga mos vaqtni belgilab olsak.',
  recommendedTasks: [],
  confidence: 0.9,
  evidenceMessageIds: [1001, 1002],
};

describe('AnalyzeConversationDto', () => {
  it('rejects a conversation with fewer than two messages', async () => {
    const dto = plainToInstance(AnalyzeConversationDto, {
      leadId: 42,
      managerId: '77',
      messages: [],
    });

    const errors = await validate(dto);

    expect(errors.some((error) => error.property === 'messages')).toBe(true);
  });

  it('accepts bounded manager and customer messages', async () => {
    const dto = plainToInstance(AnalyzeConversationDto, {
      leadId: 42,
      managerId: '77',
      crmStatus: 'Birinchi kontakt',
      messages: [
        {
          id: 1001,
          role: ConversationRole.CUSTOMER,
          text: 'Narxi qancha?',
          sentAt: '2026-07-31T10:00:00Z',
        },
        {
          id: 1002,
          role: ConversationRole.MANAGER,
          text: 'Avval vazifangizni aniqlab olaylik.',
          sentAt: '2026-07-31T10:01:00Z',
        },
      ],
    });

    const errors = await validate(dto);

    expect(errors).toEqual([]);
  });
});

describe('NegotiationsController conversation analysis', () => {
  it('forwards the authenticated organization, actor and DTO to the service', async () => {
    const service = {
      analyzeConversation: jest.fn().mockResolvedValue(validAnalysis),
    };
    const controller = new NegotiationsController(service as never);
    const dto = plainToInstance(AnalyzeConversationDto, {
      leadId: 42,
      managerId: '77',
      messages: [
        {
          id: 1001,
          role: ConversationRole.CUSTOMER,
          text: 'Narxi qancha?',
          sentAt: '2026-07-31T10:00:00Z',
        },
        {
          id: 1002,
          role: ConversationRole.MANAGER,
          text: 'Vazifangizni aniqlab olaylik.',
          sentAt: '2026-07-31T10:01:00Z',
        },
      ],
    });

    const result = await controller.analyzeConversation('org-1', { id: 'actor-9' }, dto);

    expect(service.analyzeConversation).toHaveBeenCalledWith('org-1', 'actor-9', dto);
    expect(result).toEqual(validAnalysis);
  });
});

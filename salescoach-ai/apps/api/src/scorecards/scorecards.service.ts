import { Injectable, NotFoundException, ForbiddenException } from '@nestjs/common';
import { PrismaService } from '../common/prisma.service';

@Injectable()
export class ScorecardsService {
  constructor(private prisma: PrismaService) {}

  async findByCall(callId: string, orgId: string) {
    const call = await this.prisma.call.findUnique({ where: { id: callId } });
    if (!call) throw new NotFoundException('Call not found');
    if (call.orgId !== orgId) throw new ForbiddenException();

    const scorecard = await this.prisma.scorecard.findUnique({ where: { callId } });
    if (!scorecard) throw new NotFoundException('Scorecard not ready yet');
    return scorecard;
  }

  async listByOrg(orgId: string, limit = 20, offset = 0) {
    return this.prisma.scorecard.findMany({
      where: { call: { orgId } },
      include: { call: { select: { id: true, customerName: true, createdAt: true, managerId: true } } },
      orderBy: { createdAt: 'desc' },
      take: limit,
      skip: offset,
    });
  }
}

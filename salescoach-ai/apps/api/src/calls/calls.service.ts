import { Injectable, NotFoundException, ForbiddenException, Inject } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Queue } from 'bullmq';
import { PrismaService } from '../common/prisma.service';
import { StorageService } from './storage.service';
import { TRANSCRIPTION_QUEUE } from '../common/queue.module';
import { CreateCallDto } from './dto/create-call.dto';

@Injectable()
export class CallsService {
  constructor(
    private prisma: PrismaService,
    private storage: StorageService,
    private cfg: ConfigService,
    @Inject(`QUEUE_${TRANSCRIPTION_QUEUE.toUpperCase()}`) private transcriptionQueue: Queue,
  ) {}

  async initiateUpload(orgId: string, managerId: string, dto: CreateCallDto) {
    const call = await this.prisma.call.create({
      data: {
        orgId,
        managerId,
        customerPhone: dto.customerPhone ?? null,
        customerName: dto.customerName ?? null,
        direction: dto.direction ?? 'OUTBOUND',
        status: 'UPLOADED',
      },
    });

    const audioKey = `calls/${orgId}/${call.id}/audio.${dto.ext ?? 'mp3'}`;
    const uploadUrl = await this.storage.presignedUpload(audioKey, dto.contentType ?? 'audio/mpeg');

    await this.prisma.call.update({ where: { id: call.id }, data: { audioKey } });

    return { callId: call.id, uploadUrl, audioKey };
  }

  async confirmUpload(callId: string, orgId: string) {
    const call = await this.getOrgCall(callId, orgId);
    if (!call.audioKey) throw new ForbiddenException('Audio key missing');

    await this.prisma.call.update({ where: { id: callId }, data: { status: 'TRANSCRIBING' } });
    await this.transcriptionQueue.add('transcribe', { callId, audioKey: call.audioKey });

    return { callId, status: 'TRANSCRIBING' };
  }

  async findAll(orgId: string, managerId?: string) {
    return this.prisma.call.findMany({
      where: { orgId, ...(managerId ? { managerId } : {}) },
      orderBy: { createdAt: 'desc' },
      include: { scorecard: { select: { overallScore: true } } },
    });
  }

  async findOne(callId: string, orgId: string) {
    const call = await this.prisma.call.findUnique({
      where: { id: callId },
      include: { scorecard: true },
    });
    if (!call) throw new NotFoundException('Call not found');
    if (call.orgId !== orgId) throw new ForbiddenException();

    const audioUrl = call.audioKey ? await this.storage.presignedDownload(call.audioKey) : null;

    // Transform stageScores array → object for frontend consumption
    let scorecard: any = null;
    if (call.scorecard) {
      const stageArr: { stage: string; score: number; reasoning: string }[] =
        Array.isArray(call.scorecard.stageScores) ? (call.scorecard.stageScores as any) : [];
      const stageScoresObj: Record<string, number> = {};
      for (const s of stageArr) stageScoresObj[s.stage] = s.score;

      scorecard = {
        ...call.scorecard,
        stageScores: stageScoresObj,
      };
    }

    return { ...call, scorecard, audioUrl };
  }

  async getTranscript(callId: string, orgId: string) {
    await this.getOrgCall(callId, orgId);
    return this.prisma.transcriptSegment.findMany({
      where: { callId },
      orderBy: { seq: 'asc' },
    });
  }

  private async getOrgCall(callId: string, orgId: string) {
    const call = await this.prisma.call.findUnique({ where: { id: callId } });
    if (!call) throw new NotFoundException('Call not found');
    if (call.orgId !== orgId) throw new ForbiddenException();
    return call;
  }
}

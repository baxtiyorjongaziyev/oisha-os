import { Inject, Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Queue } from 'bullmq';
import { PrismaService } from '../../common/prisma.service';
import { SCORING_QUEUE } from '../../common/queue.module';
import { FirefliesClient, NormalizedTranscript } from './fireflies.client';
import { GongClient } from './gong.client';

type Lang = 'UZ' | 'RU' | 'EN';

/**
 * Call Intelligence ingestion: external transcript (Fireflies / Gong) →
 * Call + TranscriptSegment rows → scoring queue. Skips audio upload &
 * transcription since these sources already provide diarized text.
 */
@Injectable()
export class CallIntelService {
  private readonly logger = new Logger(CallIntelService.name);
  private cachedManager: { orgId: string; managerId: string } | null = null;

  constructor(
    private readonly prisma: PrismaService,
    private readonly cfg: ConfigService,
    private readonly fireflies: FirefliesClient,
    private readonly gong: GongClient,
    @Inject(`QUEUE_${SCORING_QUEUE.toUpperCase()}`) private readonly scoringQueue: Queue,
  ) {}

  async ingestFromFireflies(transcriptId: string): Promise<{ callId: string } | null> {
    const t = await this.fireflies.fetchTranscript(transcriptId);
    if (!t || t.segments.length === 0) {
      this.logger.warn(`Fireflies transcript ${transcriptId} empty/not found`);
      return null;
    }
    return this.ingest('fireflies', t);
  }

  async ingestFromGong(callId: string): Promise<{ callId: string } | null> {
    const t = await this.gong.fetchTranscript(callId);
    if (!t || t.segments.length === 0) {
      this.logger.warn(`Gong transcript ${callId} empty/not found`);
      return null;
    }
    return this.ingest('gong', t);
  }

  private async ingest(
    source: string,
    t: NormalizedTranscript,
  ): Promise<{ callId: string } | null> {
    const identity = await this.resolveManager();
    if (!identity) {
      this.logger.error('Call-intel: no organization/manager to attribute the call to');
      return null;
    }

    const lang = (this.cfg.get<string>('CALL_INTEL_DEFAULT_LANG') ?? 'UZ').toUpperCase() as Lang;
    const lastEnd = t.segments[t.segments.length - 1]?.end ?? 0;
    const durationSec = t.durationSec ?? (Math.round(lastEnd) || null);

    const call = await this.prisma.call.create({
      data: {
        orgId: identity.orgId,
        managerId: identity.managerId,
        customerName: t.customerName ?? `${source}:${t.externalId}`,
        direction: 'INBOUND',
        language: lang,
        durationSec,
        status: 'SCORING',
      },
    });

    await this.prisma.transcriptSegment.createMany({
      data: t.segments.map((s, i) => ({
        callId: call.id,
        speaker: s.speaker,
        text: s.text,
        start: s.start,
        end: s.end,
        seq: i,
      })),
    });

    await this.scoringQueue.add('score', { callId: call.id });

    this.logger.log(`Ingested ${source} transcript ${t.externalId} → call ${call.id} (scoring)`);
    return { callId: call.id };
  }

  private async resolveManager(): Promise<{ orgId: string; managerId: string } | null> {
    if (this.cachedManager) return this.cachedManager;

    const configuredOrgId = this.cfg.get<string>('SERVICE_ORG_ID');
    const org = configuredOrgId
      ? await this.prisma.organization.findUnique({ where: { id: configuredOrgId } })
      : await this.prisma.organization.findFirst({ orderBy: { createdAt: 'asc' } });
    if (!org) return null;

    const manager = await this.prisma.user.findFirst({
      where: { orgId: org.id },
      orderBy: { createdAt: 'asc' },
    });
    if (!manager) return null;

    this.cachedManager = { orgId: org.id, managerId: manager.id };
    return this.cachedManager;
  }
}

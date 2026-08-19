import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { PrismaService } from '../../common/prisma.service';
import { MetaSellClient } from './metasell.client';

/**
 * MetaSell ingestion: pulls the Python core's aggregated seller conversion
 * report (GET /api/ai/conversion/overview) and stores one snapshot row per
 * seller. Append-only — each sync run adds a new set of rows, giving a
 * natural trend history without needing to reconcile against Call/Scorecard
 * (MetaSell data is manager x time-window aggregate, not per-call).
 */
@Injectable()
export class MetaSellService {
  private readonly logger = new Logger(MetaSellService.name);
  private cachedOrgId: string | null = null;

  constructor(
    private readonly prisma: PrismaService,
    private readonly cfg: ConfigService,
    private readonly client: MetaSellClient,
  ) {}

  async syncSnapshot(days: number): Promise<{ ok: boolean; created: number; reason?: string }> {
    const orgId = await this.resolveOrgId();
    if (!orgId) {
      return { ok: false, created: 0, reason: 'no organization to attribute snapshot to' };
    }

    const overview = await this.client.getConversionOverview(days);
    if (!overview) {
      return { ok: false, created: 0, reason: 'metasell overview fetch failed or disabled' };
    }
    if (!overview.has_data || !Array.isArray(overview.sellers) || overview.sellers.length === 0) {
      return { ok: true, created: 0, reason: 'no seller data for this period' };
    }

    const rows = overview.sellers.map((s) => ({
      orgId,
      source: 'METASELL' as const,
      periodDays: days,
      managerName: s.manager_name,
      totalCalls: s.total_calls,
      convertedCalls: s.converted_calls,
      conversionRate: s.conversion_rate,
      avgScore: s.avg_score,
      growthStage: s.growth_stage ?? null,
      growthStageLabel: s.growth_stage_label ?? null,
      revenueWon: s.revenue_won ?? null,
      revenueAtRisk: s.revenue_at_risk ?? null,
      dealsWon: s.deals_won ?? null,
      dealsLost: s.deals_lost ?? null,
      topWeaknesses: s.top_weaknesses ?? [],
      topObjections: s.top_objections ?? [],
      raw: s as object,
    }));

    await this.prisma.externalScoreSnapshot.createMany({ data: rows });
    this.logger.log(`MetaSell sync: ${rows.length} seller snapshot(s) stored (days=${days})`);
    return { ok: true, created: rows.length };
  }

  private async resolveOrgId(): Promise<string | null> {
    if (this.cachedOrgId) return this.cachedOrgId;
    const configuredOrgId = this.cfg.get<string>('SERVICE_ORG_ID');
    const org = configuredOrgId
      ? await this.prisma.organization.findUnique({ where: { id: configuredOrgId } })
      : await this.prisma.organization.findFirst({ orderBy: { createdAt: 'asc' } });
    if (!org) return null;
    this.cachedOrgId = org.id;
    return this.cachedOrgId;
  }
}

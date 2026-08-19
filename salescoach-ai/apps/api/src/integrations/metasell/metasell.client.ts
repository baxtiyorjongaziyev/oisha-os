import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';

export interface SellerDiagnosis {
  manager_name: string;
  total_calls: number;
  converted_calls: number;
  conversion_rate: number;
  avg_score: number;
  growth_stage: string | null;
  growth_stage_label: string | null;
  growth_gap: number | null;
  drill: string | null;
  top_weaknesses: string[];
  top_objections: string[];
  projected_lift: number | null;
  has_diagnosis: boolean;
  reason: string | null;
  revenue_won: number | null;
  revenue_at_risk: number | null;
  deals_won: number | null;
  deals_lost: number | null;
}

export interface ConversionOverview {
  days: number;
  total_calls: number;
  converted_calls: number;
  conversion_rate: number;
  avg_score: number;
  sellers: SellerDiagnosis[];
  has_data: boolean;
  [key: string]: unknown;
}

/**
 * Thin read-only client for the Python core's MetaSell conversion API.
 * Mirrors src/services/core/salescoach_sync.py's config-driven pattern,
 * but in the opposite direction (salescoach-ai -> Oisha-OS).
 */
@Injectable()
export class MetaSellClient {
  private readonly logger = new Logger(MetaSellClient.name);

  private get baseUrl(): string {
    return (this.cfg.get<string>('METASELL_API_URL') ?? '').replace(/\/+$/, '');
  }

  private get token(): string {
    return this.cfg.get<string>('METASELL_API_TOKEN') ?? '';
  }

  constructor(private readonly cfg: ConfigService) {}

  get enabled(): boolean {
    return Boolean(this.baseUrl && this.token);
  }

  async getConversionOverview(days: number): Promise<ConversionOverview | null> {
    if (!this.enabled) {
      this.logger.warn('MetaSell bridge not configured (METASELL_API_URL/METASELL_API_TOKEN)');
      return null;
    }
    try {
      const res = await fetch(
        `${this.baseUrl}/api/ai/conversion/overview?days=${encodeURIComponent(days)}`,
        {
          method: 'GET',
          headers: {
            Authorization: `Bearer ${this.token}`,
            Accept: 'application/json',
          },
        },
      );
      if (!res.ok) {
        this.logger.warn(`MetaSell overview fetch failed: ${res.status}`);
        return null;
      }
      return (await res.json()) as ConversionOverview;
    } catch (err) {
      this.logger.warn(`MetaSell overview fetch error: ${(err as Error)?.message}`);
      return null;
    }
  }
}

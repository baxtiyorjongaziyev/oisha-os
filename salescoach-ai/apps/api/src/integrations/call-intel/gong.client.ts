import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import type { NormalizedTranscript, NormalizedSegment } from './fireflies.client';

/**
 * Gong.io REST client — fetches a call transcript by call id.
 * Auth: Basic base64(GONG_ACCESS_KEY:GONG_ACCESS_SECRET).
 *
 * Gong returns speakerId per sentence; role is resolved from the call's
 * parties (affiliation "Internal" → manager, else customer). If parties
 * can't be resolved, the first speakerId seen is treated as the manager.
 */
@Injectable()
export class GongClient {
  private readonly logger = new Logger(GongClient.name);
  private readonly base = 'https://api.gong.io/v2';

  constructor(private readonly cfg: ConfigService) {}

  get enabled(): boolean {
    return !!(
      this.cfg.get<string>('GONG_ACCESS_KEY') && this.cfg.get<string>('GONG_ACCESS_SECRET')
    );
  }

  private authHeader(): string | null {
    const key = this.cfg.get<string>('GONG_ACCESS_KEY');
    const secret = this.cfg.get<string>('GONG_ACCESS_SECRET');
    if (!key || !secret) return null;
    return 'Basic ' + Buffer.from(`${key}:${secret}`).toString('base64');
  }

  async fetchTranscript(callId: string): Promise<NormalizedTranscript | null> {
    const auth = this.authHeader();
    if (!auth) return null;

    try {
      const roleBySpeaker = await this.resolveParties(callId, auth);

      const res = await fetch(`${this.base}/calls/transcript`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: auth },
        body: JSON.stringify({ filter: { callIds: [callId] } }),
      });

      if (!res.ok) {
        this.logger.warn(`Gong API ${res.status}: ${(await res.text()).slice(0, 200)}`);
        return null;
      }

      const json: any = await res.json();
      const callTranscript = json?.callTranscripts?.[0];
      const monologues: any[] = callTranscript?.transcript ?? [];

      let firstSpeaker: string | null = null;
      const segments: NormalizedSegment[] = [];

      for (const mono of monologues) {
        const speakerId: string = mono.speakerId ?? 'unknown';
        if (firstSpeaker === null) firstSpeaker = speakerId;

        const role =
          roleBySpeaker[speakerId] ?? (speakerId === firstSpeaker ? 'manager' : 'customer');

        for (const sentence of mono.sentences ?? []) {
          segments.push({
            speaker: role,
            text: sentence.text ?? '',
            start: Number(sentence.start ?? 0) / 1000,
            end: Number(sentence.end ?? sentence.start ?? 0) / 1000,
          });
        }
      }

      return { externalId: callId, segments };
    } catch (err: any) {
      this.logger.warn(`Gong fetch failed: ${err.message}`);
      return null;
    }
  }

  private async resolveParties(
    callId: string,
    auth: string,
  ): Promise<Record<string, 'manager' | 'customer'>> {
    const map: Record<string, 'manager' | 'customer'> = {};
    try {
      const res = await fetch(`${this.base}/calls/extensive`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: auth },
        body: JSON.stringify({
          filter: { callIds: [callId] },
          contentSelector: { exposedFields: { parties: true } },
        }),
      });
      if (!res.ok) return map;
      const json: any = await res.json();
      const parties: any[] = json?.calls?.[0]?.parties ?? [];
      for (const p of parties) {
        if (!p.speakerId) continue;
        map[p.speakerId] = p.affiliation === 'Internal' ? 'manager' : 'customer';
      }
    } catch {
      // best-effort — fall back to first-speaker heuristic
    }
    return map;
  }
}

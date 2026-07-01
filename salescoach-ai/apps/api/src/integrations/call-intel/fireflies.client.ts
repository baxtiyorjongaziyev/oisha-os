import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';

export interface NormalizedSegment {
  speaker: 'manager' | 'customer';
  text: string;
  start: number;
  end: number;
}

export interface NormalizedTranscript {
  externalId: string;
  title?: string;
  durationSec?: number;
  customerName?: string;
  segments: NormalizedSegment[];
}

/**
 * Fireflies.ai GraphQL client — fetches a transcript by meeting/transcript id.
 * Auth: Bearer FIREFLIES_API_KEY.
 *
 * Speaker→role mapping: a speaker whose name matches FIREFLIES_MANAGER_NAME
 * (case-insensitive substring) is the manager; everyone else is the customer.
 * If no match, the first speaker encountered is treated as the manager.
 */
@Injectable()
export class FirefliesClient {
  private readonly logger = new Logger(FirefliesClient.name);
  private readonly endpoint = 'https://api.fireflies.ai/graphql';

  constructor(private readonly cfg: ConfigService) {}

  get enabled(): boolean {
    return !!this.cfg.get<string>('FIREFLIES_API_KEY');
  }

  async fetchTranscript(transcriptId: string): Promise<NormalizedTranscript | null> {
    const apiKey = this.cfg.get<string>('FIREFLIES_API_KEY');
    if (!apiKey) return null;

    const query = `
      query Transcript($id: String!) {
        transcript(id: $id) {
          id
          title
          duration
          sentences { text speaker_name start_time end_time }
        }
      }`;

    try {
      const res = await fetch(this.endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${apiKey}`,
        },
        body: JSON.stringify({ query, variables: { id: transcriptId } }),
      });

      if (!res.ok) {
        this.logger.warn(`Fireflies API ${res.status}: ${(await res.text()).slice(0, 200)}`);
        return null;
      }

      const json: any = await res.json();
      const t = json?.data?.transcript;
      if (!t) return null;

      const managerName = (this.cfg.get<string>('FIREFLIES_MANAGER_NAME') ?? '').toLowerCase();
      let firstSpeaker: string | null = null;

      const segments: NormalizedSegment[] = (t.sentences ?? []).map((s: any) => {
        const speakerName: string = s.speaker_name ?? 'Speaker';
        if (firstSpeaker === null) firstSpeaker = speakerName;

        const isManager = managerName
          ? speakerName.toLowerCase().includes(managerName)
          : speakerName === firstSpeaker;

        return {
          speaker: isManager ? 'manager' : 'customer',
          text: s.text ?? '',
          start: Number(s.start_time ?? 0),
          end: Number(s.end_time ?? s.start_time ?? 0),
        };
      });

      const result: NormalizedTranscript = {
        externalId: t.id ?? transcriptId,
        segments,
      };
      if (t.title) result.title = t.title;
      if (t.duration) result.durationSec = Math.round(Number(t.duration));
      return result;
    } catch (err: any) {
      this.logger.warn(`Fireflies fetch failed: ${err.message}`);
      return null;
    }
  }
}

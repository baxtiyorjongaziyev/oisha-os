import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';

interface AmoContact {
  id: number;
  name: string;
  custom_fields_values: Array<{ field_code: string; values: Array<{ value: string }> }>;
}

@Injectable()
export class AmoCrmService {
  private readonly logger = new Logger(AmoCrmService.name);
  private readonly baseUrl: string;
  private accessToken: string | null = null;

  constructor(private cfg: ConfigService) {
    const subdomain = cfg.get('AMOCRM_SUBDOMAIN');
    this.baseUrl = subdomain ? `https://${subdomain}.amocrm.ru/api/v4` : '';
  }

  private async getToken(): Promise<string> {
    if (this.accessToken) return this.accessToken;

    const res = await fetch(`${this.baseUrl}/oauth2/access_token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        client_id: this.cfg.get('AMOCRM_CLIENT_ID'),
        client_secret: this.cfg.get('AMOCRM_CLIENT_SECRET'),
        grant_type: 'client_credentials',
      }),
    });

    if (!res.ok) throw new Error('AmoCRM auth failed');
    const data = await res.json();
    this.accessToken = data.access_token;
    setTimeout(() => { this.accessToken = null; }, (data.expires_in - 60) * 1000);
    return this.accessToken!;
  }

  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    if (!this.baseUrl) throw new Error('AMOCRM_SUBDOMAIN not configured');
    const token = await this.getToken();
    const res = await fetch(`${this.baseUrl}${path}`, {
      ...options,
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });
    if (!res.ok) throw new Error(`AmoCRM ${path} → ${res.status}`);
    return res.json();
  }

  async pushCallNote(phone: string, callId: string, score: number, summary: string) {
    try {
      const contacts = await this.request<any>(`/contacts?query=${encodeURIComponent(phone)}`);
      const contactId = contacts?._embedded?.contacts?.[0]?.id;
      if (!contactId) {
        this.logger.warn(`No AmoCRM contact for phone ${phone}`);
        return;
      }

      await this.request(`/contacts/${contactId}/notes`, {
        method: 'POST',
        body: JSON.stringify([{
          note_type: 'common',
          params: { text: `[SalesCoach AI] Call ${callId}\nScore: ${score}/100\n\n${summary}` },
        }]),
      });
    } catch (err: any) {
      this.logger.error(`AmoCRM pushCallNote failed: ${err.message}`);
    }
  }
}

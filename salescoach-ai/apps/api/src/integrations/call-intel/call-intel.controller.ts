import {
  Body,
  Controller,
  Headers,
  Post,
  Param,
  UnauthorizedException,
} from '@nestjs/common';
import { ApiOperation, ApiTags } from '@nestjs/swagger';
import { ConfigService } from '@nestjs/config';
import { CallIntelService } from './call-intel.service';

/**
 * External call-intelligence webhooks (Fireflies / Gong).
 *
 * NOT behind JWT — these are called by third-party services. Each endpoint
 * verifies a shared `x-webhook-secret` header against the configured secret.
 * If the secret is not configured, the endpoint rejects all requests.
 */
@ApiTags('integrations/call-intel')
@Controller('integrations/call-intel')
export class CallIntelController {
  constructor(
    private readonly service: CallIntelService,
    private readonly cfg: ConfigService,
  ) {}

  @Post('fireflies')
  @ApiOperation({ summary: 'Fireflies webhook — ingest transcript on completion' })
  async fireflies(
    @Headers('x-webhook-secret') secret: string,
    @Body() body: Record<string, any>,
  ) {
    this.verify(secret, 'FIREFLIES_WEBHOOK_SECRET');
    const id = body?.meetingId ?? body?.transcriptId ?? body?.id;
    if (!id) return { ok: false, reason: 'no meetingId in payload' };
    const res = await this.service.ingestFromFireflies(String(id));
    return { ok: !!res, ...res };
  }

  @Post('gong')
  @ApiOperation({ summary: 'Gong webhook — ingest transcript when call processed' })
  async gong(
    @Headers('x-webhook-secret') secret: string,
    @Body() body: Record<string, any>,
  ) {
    this.verify(secret, 'GONG_WEBHOOK_SECRET');
    const id = body?.callId ?? body?.callIds?.[0] ?? body?.objectId;
    if (!id) return { ok: false, reason: 'no callId in payload' };
    const res = await this.service.ingestFromGong(String(id));
    return { ok: !!res, ...res };
  }

  @Post('ingest/:source/:id')
  @ApiOperation({ summary: 'Manual ingest by source + external id (secret-protected)' })
  async manual(
    @Headers('x-webhook-secret') secret: string,
    @Param('source') source: string,
    @Param('id') id: string,
  ) {
    const secretKey = source === 'gong' ? 'GONG_WEBHOOK_SECRET' : 'FIREFLIES_WEBHOOK_SECRET';
    this.verify(secret, secretKey);
    const res =
      source === 'gong'
        ? await this.service.ingestFromGong(id)
        : await this.service.ingestFromFireflies(id);
    return { ok: !!res, ...res };
  }

  private verify(provided: string | undefined, configKey: string) {
    const expected = this.cfg.get<string>(configKey);
    if (!expected || provided !== expected) {
      throw new UnauthorizedException('Invalid or missing webhook secret');
    }
  }
}

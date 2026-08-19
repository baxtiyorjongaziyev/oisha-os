import {
  Controller,
  Headers,
  Post,
  Query,
  UnauthorizedException,
} from '@nestjs/common';
import { ApiOperation, ApiTags } from '@nestjs/swagger';
import { ConfigService } from '@nestjs/config';
import { MetaSellService } from './metasell.service';

/**
 * MetaSell bridge — pulls Oisha-OS's seller conversion report on demand.
 *
 * NOT behind JWT — same shared-secret pattern as call-intel's admin-trigger
 * endpoint. No scheduler exists in this codebase; sync is manually or
 * externally (ops cron / curl) triggered.
 */
@ApiTags('integrations/metasell')
@Controller('integrations/metasell')
export class MetaSellController {
  constructor(
    private readonly service: MetaSellService,
    private readonly cfg: ConfigService,
  ) {}

  @Post('sync')
  @ApiOperation({ summary: 'Pull latest MetaSell seller conversion snapshot (secret-protected)' })
  async sync(
    @Headers('x-webhook-secret') secret: string,
    @Query('days') daysParam?: string,
  ) {
    this.verify(secret);
    const days = Math.max(1, Math.min(365, Number(daysParam) || 30));
    return this.service.syncSnapshot(days);
  }

  private verify(provided: string | undefined) {
    const expected = this.cfg.get<string>('METASELL_SYNC_SECRET');
    if (!expected || provided !== expected) {
      throw new UnauthorizedException('Invalid or missing webhook secret');
    }
  }
}

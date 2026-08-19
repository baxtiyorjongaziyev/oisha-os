import { Module } from '@nestjs/common';
import { MetaSellService } from './metasell.service';
import { MetaSellController } from './metasell.controller';
import { MetaSellClient } from './metasell.client';

/**
 * MetaSell: pulls Oisha-OS's aggregated seller conversion report into a
 * separate ExternalScoreSnapshot table. PrismaModule is global, so no extra
 * imports beyond the local providers.
 */
@Module({
  controllers: [MetaSellController],
  providers: [MetaSellService, MetaSellClient],
  exports: [MetaSellService],
})
export class MetaSellModule {}

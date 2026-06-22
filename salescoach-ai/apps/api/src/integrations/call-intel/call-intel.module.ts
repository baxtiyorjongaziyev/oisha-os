import { Module } from '@nestjs/common';
import { CallIntelService } from './call-intel.service';
import { CallIntelController } from './call-intel.controller';
import { FirefliesClient } from './fireflies.client';
import { GongClient } from './gong.client';

/**
 * Call Intelligence: ingest Fireflies / Gong transcripts into the scoring
 * pipeline. PrismaModule and QueueModule are global, so no extra imports.
 */
@Module({
  controllers: [CallIntelController],
  providers: [CallIntelService, FirefliesClient, GongClient],
  exports: [CallIntelService],
})
export class CallIntelModule {}

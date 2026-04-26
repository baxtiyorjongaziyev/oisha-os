import { Module } from '@nestjs/common';
import { CallsController } from './calls.controller';
import { CallsService } from './calls.service';
import { StorageService } from './storage.service';

@Module({
  controllers: [CallsController],
  providers: [CallsService, StorageService],
  exports: [CallsService],
})
export class CallsModule {}

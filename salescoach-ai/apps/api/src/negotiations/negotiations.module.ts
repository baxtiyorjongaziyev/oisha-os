import { Module } from '@nestjs/common';
import { NegotiationsController } from './negotiations.controller';
import { NegotiationsService } from './negotiations.service';

@Module({
  controllers: [NegotiationsController],
  providers: [NegotiationsService],
  exports: [NegotiationsService],
})
export class NegotiationsModule {}

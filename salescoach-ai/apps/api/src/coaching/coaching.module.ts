import { Module } from '@nestjs/common';
import { CoachingGateway } from './coaching.gateway';
import { NegotiationsModule } from '../negotiations/negotiations.module';

@Module({
  imports: [NegotiationsModule],
  providers: [CoachingGateway],
})
export class CoachingModule {}

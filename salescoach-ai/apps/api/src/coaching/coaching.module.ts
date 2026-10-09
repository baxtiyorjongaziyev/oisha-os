import { Module } from '@nestjs/common';
import { CoachingGateway } from './coaching.gateway';
import { NegotiationsModule } from '../negotiations/negotiations.module';
import { AuthModule } from '../auth/auth.module';
import { PrismaModule } from '../common/prisma.module';

@Module({
  imports: [NegotiationsModule, AuthModule, PrismaModule],
  providers: [CoachingGateway],
})
export class CoachingModule {}

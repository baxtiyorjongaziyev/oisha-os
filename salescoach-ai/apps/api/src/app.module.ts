import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { ThrottlerModule } from '@nestjs/throttler';
import { HealthModule } from './health/health.module';
import { AuthModule } from './auth/auth.module';
import { UsersModule } from './users/users.module';
import { OrganizationsModule } from './organizations/organizations.module';
import { CallsModule } from './calls/calls.module';
import { ScorecardsModule } from './scorecards/scorecards.module';
import { SharesModule } from './shares/shares.module';
import { PrismaModule } from './common/prisma.module';
import { QueueModule } from './common/queue.module';

@Module({
  imports: [
    ConfigModule.forRoot({ isGlobal: true }),
    ThrottlerModule.forRoot([{ ttl: 60_000, limit: 100 }]),
    PrismaModule,
    QueueModule,
    HealthModule,
    AuthModule,
    UsersModule,
    OrganizationsModule,
    CallsModule,
    ScorecardsModule,
    SharesModule,
  ],
})
export class AppModule {}

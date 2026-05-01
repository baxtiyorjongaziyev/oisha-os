import { Global, Module } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Queue, Worker } from 'bullmq';

export const TRANSCRIPTION_QUEUE = 'transcription';
export const SCORING_QUEUE = 'scoring';

const queues = [TRANSCRIPTION_QUEUE, SCORING_QUEUE].map((name) => ({
  provide: `QUEUE_${name.toUpperCase()}`,
  useFactory: (cfg: ConfigService) =>
    new Queue(name, {
      connection: { host: cfg.get('REDIS_HOST', 'localhost'), port: cfg.get<number>('REDIS_PORT', 6379) },
    }),
  inject: [ConfigService],
}));

@Global()
@Module({
  providers: queues,
  exports: queues.map((q) => q.provide),
})
export class QueueModule {}

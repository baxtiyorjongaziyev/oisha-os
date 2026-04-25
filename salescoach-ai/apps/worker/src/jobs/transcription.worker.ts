import { Worker, Job } from 'bullmq';
import { redis } from '../services/redis';
import { prisma } from '../services/prisma';
import { WhisperService } from '../services/whisper.service';

const QUEUE_NAME = 'transcription';

export class TranscriptionWorker {
  private worker: Worker;
  private whisper = new WhisperService();

  start() {
    this.worker = new Worker(QUEUE_NAME, this.process.bind(this), {
      connection: redis,
      concurrency: 2,
    });

    this.worker.on('failed', (job, err) => {
      console.error(`[transcription] Job ${job?.id} failed:`, err.message);
    });
  }

  async stop() {
    await this.worker.close();
  }

  private async process(job: Job<{ callId: string; audioKey: string }>) {
    const { callId, audioKey } = job.data;
    console.log(`[transcription] Processing call ${callId}`);

    try {
      await prisma.call.update({ where: { id: callId }, data: { status: 'TRANSCRIBING' } });

      const { segments, language, durationSec } = await this.whisper.transcribe(audioKey);

      await prisma.$transaction([
        prisma.transcriptSegment.deleteMany({ where: { callId } }),
        prisma.transcriptSegment.createMany({
          data: segments.map((s) => ({ callId, ...s })),
        }),
        prisma.call.update({
          where: { id: callId },
          data: {
            status: 'SCORING',
            language: language.toUpperCase() as any,
            durationSec,
          },
        }),
      ]);

      // Enqueue scoring
      const { Queue } = await import('bullmq');
      const scoringQueue = new Queue('scoring', { connection: redis });
      await scoringQueue.add('score', { callId });
    } catch (err: any) {
      await prisma.call.update({
        where: { id: callId },
        data: { status: 'FAILED', errorMessage: err.message },
      });
      throw err;
    }
  }
}

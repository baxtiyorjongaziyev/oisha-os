import { Worker, Job } from 'bullmq';
import { redis } from '../services/redis';
import { prisma } from '../services/prisma';
import { WhisperService } from '../services/whisper.service';
import { DiarizationService } from '../services/diarization.service';

const QUEUE_NAME = 'transcription';

export class TranscriptionWorker {
  private worker!: Worker;
  private whisper = new WhisperService();
  private diarization = new DiarizationService();

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

    let tmpDir: string | undefined;
    try {
      await prisma.call.update({ where: { id: callId }, data: { status: 'TRANSCRIBING' } });

      const result = await this.whisper.transcribe(audioKey);
      tmpDir = result.tmpDir;

      // Diarize while audio file still exists in tmpDir
      const audioPath = DiarizationService.audioPathFromTmpDir(tmpDir);
      const diarized = await this.diarization.diarize(audioPath, result.segments);

      await prisma.$transaction([
        prisma.transcriptSegment.deleteMany({ where: { callId } }),
        prisma.transcriptSegment.createMany({
          data: diarized.map((s) => ({
            callId,
            speaker: s.speaker,
            start: s.start,
            end: s.end,
            text: s.text,
            seq: s.seq,
          })),
        }),
        prisma.call.update({
          where: { id: callId },
          data: {
            status: 'SCORING',
            language: result.language.toUpperCase() as any,
            durationSec: result.durationSec,
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
    } finally {
      if (tmpDir) {
        const { rm } = await import('fs/promises');
        await rm(tmpDir, { recursive: true, force: true }).catch(() => {});
      }
    }
  }
}

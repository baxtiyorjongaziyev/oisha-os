import { Worker, Job } from 'bullmq';
import { redis } from '../services/redis';
import { prisma } from '../services/prisma';
import { ScoringService } from '../services/scoring.service';
import { CoachingService } from '../services/coaching.service';
import { ObjectionService } from '../services/objection.service';

const QUEUE_NAME = 'scoring';

export class ScoringWorker {
  private worker!: Worker;
  private scorer = new ScoringService();
  private coaching = new CoachingService();
  private objection = new ObjectionService();

  start() {
    this.worker = new Worker(QUEUE_NAME, this.process.bind(this), {
      connection: redis,
      concurrency: 1,
    });

    this.worker.on('failed', (job, err) => {
      console.error(`[scoring] Job ${job?.id} failed:`, err.message);
    });
  }

  async stop() {
    await this.worker.close();
  }

  private async process(job: Job<{ callId: string }>) {
    const { callId } = job.data;
    console.log(`[scoring] Scoring call ${callId}`);

    try {
      const [call, segments] = await Promise.all([
        prisma.call.findUniqueOrThrow({ where: { id: callId } }),
        prisma.transcriptSegment.findMany({ where: { callId }, orderBy: { seq: 'asc' } }),
      ]);
      type TranscriptSegment = (typeof segments)[number];

      const transcript = segments
        .map((s: TranscriptSegment) => `[${s.speaker.toUpperCase()}] ${s.text}`)
        .join('\n');

      const language = (call.language?.toLowerCase() ?? 'uz') as 'uz' | 'ru' | 'en';
      const result = await this.scorer.score(transcript, language, call.durationSec ?? undefined);

      const managerSegs = segments.filter((s: TranscriptSegment) => s.speaker === 'manager');
      const customerSegs = segments.filter((s: TranscriptSegment) => s.speaker === 'customer');
      const totalDuration = call.durationSec ?? 1;
      const managerDuration = managerSegs.reduce(
        (acc: number, s: TranscriptSegment) => acc + (s.end - s.start),
        0,
      );
      const customerDuration = customerSegs.reduce(
        (acc: number, s: TranscriptSegment) => acc + (s.end - s.start),
        0,
      );

      const wpmWords = managerSegs.reduce(
        (acc: number, s: TranscriptSegment) => acc + s.text.split(' ').length,
        0,
      );
      const wpmMinutes = managerDuration / 60;

      // Objection analysis (non-blocking — runs in parallel with upsert)
      const objectionPromise = this.objection
        .analyze(
          callId,
          transcript,
          segments.map((s: TranscriptSegment) => ({ speaker: s.speaker, text: s.text, start: s.start })),
          language,
        )
        .catch((err) => {
          console.error(`[scoring] Objection analysis failed for ${callId}:`, err.message);
          return null;
        });

      const objectionReport = await objectionPromise;

      await prisma.scorecard.upsert({
        where: { callId },
        create: {
          callId,
          overallScore: result.overallScore,
          stageScores: result.stageScores as any,
          voiceAnalytics: {
            ...result.voiceAnalytics,
            managerTalkRatio: managerDuration / totalDuration,
            customerTalkRatio: customerDuration / totalDuration,
            wpm: wpmMinutes > 0 ? Math.round(wpmWords / wpmMinutes) : 0,
            objectionReport: objectionReport ?? null,
          } as any,
          summary: result.summary,
          goodPoints: result.goodPoints,
          improvementPoints: result.improvementPoints,
          recommendedPhrase: result.recommendedPhrase,
          nextStepCommitments: result.nextStepCommitments as any,
          riskFlags: result.riskFlags,
          leadQualityScore: result.leadQualityScore,
          predictedOutcome: result.predictedOutcome ?? null,
        },
        update: {
          overallScore: result.overallScore,
          stageScores: result.stageScores as any,
          summary: result.summary,
          voiceAnalytics: {
            ...result.voiceAnalytics,
            managerTalkRatio: managerDuration / totalDuration,
            customerTalkRatio: customerDuration / totalDuration,
            wpm: wpmMinutes > 0 ? Math.round(wpmWords / wpmMinutes) : 0,
            objectionReport: objectionReport ?? null,
          } as any,
          predictedOutcome: result.predictedOutcome ?? null,
        },
      });

      await prisma.call.update({ where: { id: callId }, data: { status: 'DONE' } });

      // Deliver coaching card to manager via Telegram (fire-and-forget)
      this.coaching.deliver(callId).catch((err) => {
        console.error(`[scoring] Coaching delivery failed for ${callId}:`, err.message);
      });
    } catch (err: any) {
      await prisma.call.update({
        where: { id: callId },
        data: { status: 'FAILED', errorMessage: err.message },
      });
      throw err;
    }
  }
}

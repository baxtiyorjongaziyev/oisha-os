import 'dotenv/config';
import { TranscriptionWorker } from './jobs/transcription.worker';
import { ScoringWorker } from './jobs/scoring.worker';

const REQUIRED_ENV = [
  'DATABASE_URL',
  'REDIS_HOST',
  'S3_BUCKET',
  'AWS_ACCESS_KEY_ID',
  'AWS_SECRET_ACCESS_KEY',
  'ANTHROPIC_API_KEY',
] as const;

function validateEnv() {
  const missing = REQUIRED_ENV.filter((key) => !process.env[key]);
  if (missing.length > 0) {
    console.error(`[worker] Missing required env vars: ${missing.join(', ')}`);
    console.error('[worker] Workers will not start — fix env and restart');
    process.exit(1);
  }
}

async function main() {
  validateEnv();

  const transcription = new TranscriptionWorker();
  const scoring = new ScoringWorker();

  transcription.start();
  scoring.start();

  console.log('[worker] Transcription + Scoring workers started');

  process.on('SIGTERM', async () => {
    await transcription.stop();
    await scoring.stop();
    process.exit(0);
  });
}

main().catch((err) => {
  console.error('[worker] Fatal:', err);
  process.exit(1);
});

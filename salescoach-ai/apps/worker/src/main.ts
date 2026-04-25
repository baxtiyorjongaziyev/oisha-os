import 'dotenv/config';
import { TranscriptionWorker } from './jobs/transcription.worker';
import { ScoringWorker } from './jobs/scoring.worker';

async function main() {
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

main().catch(console.error);

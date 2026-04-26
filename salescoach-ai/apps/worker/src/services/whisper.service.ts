import { execFile } from 'child_process';
import { promisify } from 'util';
import * as fs from 'fs/promises';
import * as path from 'path';
import * as os from 'os';
import { S3Client, GetObjectCommand } from '@aws-sdk/client-s3';
import { Readable } from 'stream';

const execFileAsync = promisify(execFile);

export interface TranscriptSegment {
  speaker: string;
  start: number;
  end: number;
  text: string;
  seq: number;
}

export class WhisperService {
  private s3: S3Client;
  private bucket: string;

  constructor() {
    this.bucket = process.env['S3_BUCKET']!;
    const endpoint = process.env['S3_ENDPOINT'];
    this.s3 = new S3Client({
      region: process.env['AWS_REGION'] ?? 'us-east-1',
      ...(endpoint ? { endpoint, forcePathStyle: process.env['S3_FORCE_PATH_STYLE'] === 'true' } : {}),
      credentials: {
        accessKeyId: process.env['AWS_ACCESS_KEY_ID']!,
        secretAccessKey: process.env['AWS_SECRET_ACCESS_KEY']!,
      },
    });
  }

  async transcribe(audioKey: string): Promise<{ segments: TranscriptSegment[]; language: string; durationSec: number }> {
    const tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), 'sc-'));
    const localFile = path.join(tmpDir, 'audio.mp3');

    try {
      await this.downloadToFile(audioKey, localFile);

      // whisper-ctranslate2 or whisper CLI — must be installed in the worker container
      const whisperModel = process.env.WHISPER_MODEL ?? 'large-v3';
      const { stdout } = await execFileAsync('whisper', [
        localFile,
        '--model', whisperModel,
        '--output_format', 'json',
        '--output_dir', tmpDir,
        '--task', 'transcribe',
      ], { timeout: 300_000 });

      const jsonPath = path.join(tmpDir, 'audio.json');
      const raw = JSON.parse(await fs.readFile(jsonPath, 'utf-8'));

      const segments: TranscriptSegment[] = raw.segments.map((s: any, i: number) => ({
        speaker: 'unknown',
        start: s.start,
        end: s.end,
        text: s.text.trim(),
        seq: i,
      }));

      return {
        segments,
        language: raw.language ?? 'uz',
        durationSec: Math.round(raw.segments.at(-1)?.end ?? 0),
      };
    } finally {
      await fs.rm(tmpDir, { recursive: true, force: true });
    }
  }

  private async downloadToFile(key: string, dest: string) {
    const { Body } = await this.s3.send(new GetObjectCommand({ Bucket: this.bucket, Key: key }));
    const stream = Body as Readable;
    const chunks: Buffer[] = [];
    for await (const chunk of stream) chunks.push(Buffer.from(chunk));
    await fs.writeFile(dest, Buffer.concat(chunks));
  }
}

import { execFile } from 'child_process';
import { promisify } from 'util';
import * as fs from 'fs/promises';
import * as path from 'path';
import type { TranscriptSegment } from './whisper.service.js';

const execFileAsync = promisify(execFile);

export interface DiarizedSegment extends TranscriptSegment {
  speaker: 'manager' | 'customer' | 'unknown';
}

/**
 * Speaker Diarization: assigns manager/customer labels to transcript segments.
 *
 * Strategy:
 *   1. Try pyannote-audio CLI (requires HF_TOKEN env var + installed model).
 *   2. Fall back to turn-based heuristic: first speaker = manager.
 *
 * Pyannote output (RTTM format):
 *   SPEAKER file 1 <start> <dur> <na> <na> <speaker_id> <na> <na>
 */
export class DiarizationService {
  async diarize(
    audioPath: string,
    segments: TranscriptSegment[],
  ): Promise<DiarizedSegment[]> {
    const hfToken = process.env['HF_TOKEN'];
    if (hfToken) {
      try {
        return await this._diarizeWithPyannote(audioPath, segments, hfToken);
      } catch {
        // fall through to heuristic
      }
    }
    return this._heuristicDiarize(segments);
  }

  private async _diarizeWithPyannote(
    audioPath: string,
    segments: TranscriptSegment[],
    hfToken: string,
  ): Promise<DiarizedSegment[]> {
    const outRttm = audioPath.replace(/\.[^.]+$/, '.rttm');

    await execFileAsync(
      'python3',
      [
        '-c',
        `
import os
from pyannote.audio import Pipeline
pipeline = Pipeline.from_pretrained(
    "pyannote/speaker-diarization-3.1",
    use_auth_token="${hfToken}"
)
diarization = pipeline("${audioPath}")
with open("${outRttm}", "w") as f:
    diarization.write_rttm(f)
`,
      ],
      { timeout: 300_000 },
    );

    const rttm = await fs.readFile(outRttm, 'utf-8');
    await fs.unlink(outRttm).catch(() => {});

    const speakerMap = this._parseRttm(rttm);
    return this._mapSegmentsToSpeakers(segments, speakerMap);
  }

  /**
   * Parses RTTM into [{start, end, speakerId}] intervals.
   */
  private _parseRttm(
    rttm: string,
  ): Array<{ start: number; end: number; speakerId: string }> {
    const intervals: Array<{ start: number; end: number; speakerId: string }> =
      [];
    for (const line of rttm.split('\n')) {
      const parts = line.trim().split(/\s+/);
      if (parts[0] !== 'SPEAKER') continue;
      const start = parseFloat(parts[3] ?? '0');
      const dur = parseFloat(parts[4] ?? '0');
      const speakerId = parts[7] ?? 'SPEAKER_00';
      intervals.push({ start, end: start + dur, speakerId });
    }
    return intervals;
  }

  /**
   * Maps transcript segments to speaker labels.
   * First unique speaker encountered = manager (they initiate the call).
   */
  private _mapSegmentsToSpeakers(
    segments: TranscriptSegment[],
    intervals: Array<{ start: number; end: number; speakerId: string }>,
  ): DiarizedSegment[] {
    const speakerOrder: string[] = [];

    const getSpeaker = (start: number, end: number): string => {
      const mid = (start + end) / 2;
      const match = intervals.find((i) => i.start <= mid && mid < i.end);
      return match?.speakerId ?? 'SPEAKER_00';
    };

    return segments.map((seg) => {
      const rawId = getSpeaker(seg.start, seg.end);
      if (!speakerOrder.includes(rawId)) speakerOrder.push(rawId);
      const role = speakerOrder.indexOf(rawId) === 0 ? 'manager' : 'customer';
      return { ...seg, speaker: role };
    });
  }

  /**
   * Heuristic fallback: alternating turns, first = manager.
   * Works well for 2-speaker sales calls where speakers rarely overlap.
   */
  private _heuristicDiarize(segments: TranscriptSegment[]): DiarizedSegment[] {
    if (segments.length === 0) return [];

    const GAP_THRESHOLD = 1.5; // seconds — longer pause = likely speaker change
    const result: DiarizedSegment[] = [];
    let currentSpeaker: 'manager' | 'customer' = 'manager';
    let lastEnd = segments[0]!.start;

    for (const seg of segments) {
      const gap = seg.start - lastEnd;
      if (gap > GAP_THRESHOLD) {
        currentSpeaker = currentSpeaker === 'manager' ? 'customer' : 'manager';
      }
      result.push({ ...seg, speaker: currentSpeaker });
      lastEnd = seg.end;
    }

    return result;
  }

  /**
   * Resolves audio file path from S3 key pattern.
   * Called after WhisperService downloads the file.
   */
  static audioPathFromTmpDir(tmpDir: string): string {
    return path.join(tmpDir, 'audio.mp3');
  }
}

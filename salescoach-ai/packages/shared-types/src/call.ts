import { z } from 'zod';
import { CallDirection, CallLanguage, CallStatus } from './enums';

export const TranscriptSegmentSchema = z.object({
  speaker: z.enum(['manager', 'customer', 'unknown']),
  start: z.number(),
  end: z.number(),
  text: z.string(),
});

export type TranscriptSegment = z.infer<typeof TranscriptSegmentSchema>;

export const CallSchema = z.object({
  id: z.string().uuid(),
  orgId: z.string().uuid(),
  managerId: z.string().uuid(),
  customerPhone: z.string().nullable(),
  customerName: z.string().nullable(),
  direction: z.nativeEnum(CallDirection),
  language: z.nativeEnum(CallLanguage).nullable(),
  durationSec: z.number().int().nullable(),
  audioUrl: z.string().nullable(),
  status: z.nativeEnum(CallStatus),
  createdAt: z.string().datetime(),
});

export type Call = z.infer<typeof CallSchema>;

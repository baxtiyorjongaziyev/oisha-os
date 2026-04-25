import { z } from "zod";

export const userRoleSchema = z.enum(["admin", "rop", "manager"]);
export type UserRole = z.infer<typeof userRoleSchema>;

export const callDirectionSchema = z.enum(["incoming", "outgoing"]);
export type CallDirection = z.infer<typeof callDirectionSchema>;

export const callStatusSchema = z.enum([
  "queued",
  "uploaded",
  "transcribing",
  "scoring",
  "done",
  "failed"
]);
export type CallStatus = z.infer<typeof callStatusSchema>;

export const transcriptSegmentSchema = z.object({
  speaker: z.enum(["manager", "customer"]),
  start: z.number().nonnegative(),
  end: z.number().nonnegative(),
  text: z.string().min(1)
});
export type TranscriptSegment = z.infer<typeof transcriptSegmentSchema>;

export const scoreStageSchema = z.object({
  stage: z.string().min(1),
  score: z.number().min(0).max(100),
  reasoning: z.string().min(1)
});
export type ScoreStage = z.infer<typeof scoreStageSchema>;

export const healthResponseSchema = z.object({
  status: z.literal("ok"),
  service: z.string().min(1),
  checkedAt: z.string().datetime()
});
export type HealthResponse = z.infer<typeof healthResponseSchema>;

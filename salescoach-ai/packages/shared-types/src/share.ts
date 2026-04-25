import { z } from 'zod';

export const ShareLinkSchema = z.object({
  id: z.string().uuid(),
  callId: z.string().uuid(),
  expiresAt: z.string().datetime(),
  createdBy: z.string().uuid(),
  revokedAt: z.string().datetime().nullable(),
  hasPassword: z.boolean(),
  accessCount: z.number().int(),
});

export type ShareLink = z.infer<typeof ShareLinkSchema>;

export const CreateShareLinkSchema = z.object({
  expiresInDays: z.number().int().min(1).max(365).default(30),
  password: z.string().min(4).max(64).optional(),
  maskCustomerName: z.boolean().default(false),
});

export type CreateShareLink = z.infer<typeof CreateShareLinkSchema>;

import { z } from 'zod';
import { UserRole } from './enums';

export const UserSchema = z.object({
  id: z.string().uuid(),
  orgId: z.string().uuid(),
  email: z.string().email(),
  role: z.nativeEnum(UserRole),
  locale: z.enum(['uz', 'ru']).default('uz'),
  createdAt: z.string().datetime(),
});

export type User = z.infer<typeof UserSchema>;

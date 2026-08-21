import { NextResponse } from 'next/server';
import { FALLBACK_TASKS } from '@/lib/apiClient';

export const dynamic = 'force-dynamic';

export async function GET() {
  return NextResponse.json({ tasks: FALLBACK_TASKS, total: FALLBACK_TASKS.length });
}

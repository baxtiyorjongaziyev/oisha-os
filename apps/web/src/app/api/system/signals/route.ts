import { NextResponse } from 'next/server';
import { FALLBACK_SIGNALS_REPORT } from '@/lib/apiClient';

export const dynamic = 'force-dynamic';

export async function GET() {
  return NextResponse.json(FALLBACK_SIGNALS_REPORT);
}

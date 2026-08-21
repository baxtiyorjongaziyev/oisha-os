import { NextResponse } from 'next/server';
import { FALLBACK_CRM_STATS } from '@/lib/apiClient';

export const dynamic = 'force-dynamic';

export async function GET() {
  return NextResponse.json(FALLBACK_CRM_STATS);
}

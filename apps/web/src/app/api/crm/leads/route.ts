import { NextResponse } from 'next/server';
import { FALLBACK_LEADS } from '@/lib/apiClient';

export const dynamic = 'force-dynamic';

export async function GET() {
  return NextResponse.json({ leads: FALLBACK_LEADS, total: 487 });
}

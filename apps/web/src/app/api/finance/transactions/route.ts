import { NextResponse } from 'next/server';
import { FALLBACK_TRANSACTIONS } from '@/lib/apiClient';

export const dynamic = 'force-dynamic';

export async function GET() {
  return NextResponse.json({ transactions: FALLBACK_TRANSACTIONS });
}

import { NextResponse } from 'next/server';
import { getSystemSignals } from '@/lib/apiClient';

export const dynamic = 'force-dynamic';

export async function GET() {
  const data = await getSystemSignals();
  return NextResponse.json(data);
}

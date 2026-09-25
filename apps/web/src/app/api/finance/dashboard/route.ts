import { NextResponse } from 'next/server';
import { getFinanceDashboardStats } from '@/lib/apiClient';

export const dynamic = 'force-dynamic';

export async function GET() {
  const data = await getFinanceDashboardStats();
  return NextResponse.json(data);
}

import { NextResponse } from 'next/server';
import { getCrmDashboardStats } from '@/lib/apiClient';

export const dynamic = 'force-dynamic';

export async function GET() {
  const stats = await getCrmDashboardStats();
  return NextResponse.json(stats);
}

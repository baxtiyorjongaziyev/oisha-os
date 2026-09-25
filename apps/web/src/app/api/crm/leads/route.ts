import { NextResponse } from 'next/server';
import { getCrmLeads } from '@/lib/apiClient';

export const dynamic = 'force-dynamic';

export async function GET() {
  const data = await getCrmLeads();
  return NextResponse.json(data);
}

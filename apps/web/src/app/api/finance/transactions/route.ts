import { NextResponse } from 'next/server';
import { getFinanceTransactions } from '@/lib/apiClient';

export const dynamic = 'force-dynamic';

export async function GET() {
  const data = await getFinanceTransactions();
  return NextResponse.json(data);
}

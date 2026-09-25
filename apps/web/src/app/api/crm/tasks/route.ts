import { NextResponse } from 'next/server';
import { getFrogTasks } from '@/lib/apiClient';

export const dynamic = 'force-dynamic';

export async function GET() {
  const data = await getFrogTasks();
  return NextResponse.json(data);
}

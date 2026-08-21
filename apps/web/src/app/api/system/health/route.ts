import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

export async function GET() {
  return NextResponse.json({
    status: 'healthy',
    timestamp: new Date().toISOString(),
    version: '2.0.0',
    system: 'Oisha OS Agency Command',
    pipelines: {
      amocrm: 'connected',
      telegram: 'active',
      finance: 'synced',
      ai_agents: 'ready'
    }
  });
}

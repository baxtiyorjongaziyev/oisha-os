import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const webhookUrl = process.env.OISHA_FEEDBACK_WEBHOOK_URL;
  if (!webhookUrl) {
    return NextResponse.json({ error: "Feedback webhook sozlanmagan" }, { status: 503 });
  }
  const body = await request.json();
  const response = await fetch(webhookUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    return NextResponse.json({ error: `Feedback provider HTTP ${response.status}` }, { status: 502 });
  }
  return NextResponse.json({ ok: true });
}

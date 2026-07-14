import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET(
  _request: NextRequest,
  context: { params: Promise<{ callId: string }> },
): Promise<NextResponse> {
  const { callId } = await context.params;
  const baseUrl = process.env.OISHA_API_URL ?? "http://127.0.0.1:8080";
  try {
    const response = await fetch(
      `${baseUrl.replace(/\/$/, "")}/api/v1/dashboard/call/${encodeURIComponent(callId)}`,
      { cache: "no-store" },
    );
    const payload = await response.json();
    return NextResponse.json(payload, { status: response.status });
  } catch (error) {
    return NextResponse.json(
      { detail: `Oisha API unavailable: ${error instanceof Error ? error.message : "unknown error"}` },
      { status: 503 },
    );
  }
}

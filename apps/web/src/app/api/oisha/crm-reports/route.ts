import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest): Promise<NextResponse> {
  const baseUrl =
    process.env.OISHA_API_URL ??
    process.env.NEXT_PUBLIC_OISHA_API_URL ??
    "http://127.0.0.1:8080";

  const headers: HeadersInit = {};
  const cookie = request.headers.get("cookie");
  if (cookie) headers["cookie"] = cookie;
  const authHeader = request.headers.get("authorization");
  if (authHeader) headers["authorization"] = authHeader;
  const apiSecret = process.env.OISHA_API_SECRET;
  if (apiSecret && !authHeader) headers["authorization"] = `Bearer ${apiSecret}`;

  const period = request.nextUrl.searchParams.get("period") ?? "daily";

  try {
    const response = await fetch(
      `${baseUrl.replace(/\/$/, "")}/api/crm/reports?period=${encodeURIComponent(period)}`,
      { cache: "no-store", headers }
    );
    const payload = await response.json();
    return NextResponse.json(payload, { status: response.status });
  } catch (error) {
    return NextResponse.json(
      {
        available: false,
        period,
        message: `Oisha API unavailable: ${
          error instanceof Error ? error.message : "unknown error"
        }`,
      },
      { status: 503 }
    );
  }
}

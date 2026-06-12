import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET(): Promise<NextResponse> {
  const baseUrl =
    process.env.OISHA_API_URL ??
    process.env.NEXT_PUBLIC_OISHA_API_URL ??
    "http://127.0.0.1:8080";

  try {
    const response = await fetch(`${baseUrl.replace(/\/$/, "")}/api/sales-quality/overview`, {
      cache: "no-store"
    });
    const payload = await response.json();
    return NextResponse.json(payload, { status: response.status });
  } catch (error) {
    return NextResponse.json(
      {
        real_data: false,
        calls: [],
        message: `Oisha API unavailable: ${error instanceof Error ? error.message : "unknown error"}`
      },
      { status: 503 }
    );
  }
}

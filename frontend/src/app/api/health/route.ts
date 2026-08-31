import { NextResponse } from "next/server";

import { backendHealth } from "@/lib/api";

export const dynamic = "force-dynamic";

export async function GET() {
  const result = await backendHealth();
  const traceHeader = result.ok ? result.traceId : result.error.traceId;

  if (result.ok) {
    return NextResponse.json(result.data, {
      status: 200,
      headers: { "Cache-Control": "no-store", "X-Request-ID": traceHeader },
    });
  }

  return NextResponse.json(
    {
      code: result.error.code,
      message: result.error.message,
      details: null,
      trace_id: result.error.traceId,
    },
    { status: 502, headers: { "Cache-Control": "no-store", "X-Request-ID": traceHeader } },
  );
}

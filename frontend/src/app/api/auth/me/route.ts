import { NextResponse, type NextRequest } from "next/server";

import { BACKEND_TIMEOUT_MS, backendUrl, newTraceId } from "@/lib/backend";
import { MeSchema } from "@/lib/schemas";
import { ACCESS_COOKIE } from "@/lib/session-cookies";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const accessToken = request.cookies.get(ACCESS_COOKIE)?.value;
  if (!accessToken) {
    return NextResponse.json(
      {
        code: "AUTHENTICATION_REQUIRED",
        message: "No session",
        details: null,
        trace_id: newTraceId(),
      },
      { status: 401 },
    );
  }

  try {
    const backendResponse = await fetch(`${backendUrl()}/auth/me`, {
      cache: "no-store",
      signal: AbortSignal.timeout(BACKEND_TIMEOUT_MS),
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "X-Request-ID": newTraceId(),
      },
    });
    if (backendResponse.ok) {
      const me = MeSchema.safeParse(await backendResponse.json());
      if (me.success) {
        return NextResponse.json(me.data, {
          status: 200,
          headers: { "Cache-Control": "no-store" },
        });
      }
    }
    const body: unknown = await backendResponse.json().catch(() => null);
    const status = backendResponse.status === 401 ? 401 : 502;
    return NextResponse.json(body ?? {
      code: "AUTHENTICATION_REQUIRED",
      message: "Session invalid",
      details: null,
      trace_id: newTraceId(),
    }, { status });
  } catch {
    return NextResponse.json(
      {
        code: "INTERNAL_ERROR",
        message: "Backend is unreachable",
        details: null,
        trace_id: newTraceId(),
      },
      { status: 502 },
    );
  }
}

import { NextResponse, type NextRequest } from "next/server";

import { backendUrl, newTraceId } from "@/lib/backend";
import { ACCESS_COOKIE } from "@/lib/session-cookies";

export const dynamic = "force-dynamic";

/**
 * SSE passthrough: forwards the access cookie as a Bearer header (browsers
 * cannot set headers on EventSource) and streams the backend response body
 * through verbatim — no buffering, no read timeout (the stream is
 * long-lived). Aborting follows the client: when the browser closes the
 * EventSource, `request.signal` tears down the upstream connection.
 */
export async function GET(request: NextRequest) {
  const accessToken = request.cookies.get(ACCESS_COOKIE)?.value;
  if (!accessToken) {
    return NextResponse.json(
      { code: "AUTHENTICATION_REQUIRED", message: "No session", details: null, trace_id: newTraceId() },
      { status: 401 },
    );
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${backendUrl()}/notifications/stream`, {
      cache: "no-store",
      headers: {
        Authorization: `Bearer ${accessToken}`,
        Accept: "text/event-stream",
        "X-Request-ID": newTraceId(),
      },
      signal: request.signal,
    });
  } catch {
    return NextResponse.json(
      { code: "INTERNAL_ERROR", message: "Backend is unreachable", details: null, trace_id: newTraceId() },
      { status: 502 },
    );
  }

  if (!upstream.ok || !upstream.body) {
    const body: unknown = await upstream.json().catch(() => null);
    return NextResponse.json(body, { status: upstream.status });
  }

  return new NextResponse(upstream.body, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      "X-Accel-Buffering": "no",
    },
  });
}

import { NextResponse, type NextRequest } from "next/server";

import { BACKEND_TIMEOUT_MS, backendUrl, newTraceId } from "@/lib/backend";
import { ACCESS_COOKIE, CSRF_COOKIE, csrfMatches } from "@/lib/session-cookies";

export type ProxyMethod = "GET" | "POST" | "PATCH" | "DELETE";

function envelope(code: string, message: string, status: number): NextResponse {
  return NextResponse.json(
    { code, message, details: null, trace_id: newTraceId() },
    { status },
  );
}

/**
 * BFF passthrough: forwards the access cookie to the backend and returns the
 * backend response (status + envelope/body) verbatim. Mutations require the
 * double-submit CSRF header. The browser never sees token material.
 */
export async function proxyToBackend(
  request: NextRequest,
  method: ProxyMethod,
  backendPath: string,
  body?: unknown,
): Promise<NextResponse> {
  const accessToken = request.cookies.get(ACCESS_COOKIE)?.value;
  if (!accessToken) {
    return envelope("AUTHENTICATION_REQUIRED", "No session", 401);
  }
  if (
    method !== "GET" &&
    !csrfMatches(request.headers.get("X-CSRF-Token"), request.cookies.get(CSRF_COOKIE)?.value)
  ) {
    return envelope("VALIDATION_ERROR", "Missing or invalid CSRF token", 403);
  }

  const search = request.nextUrl.search || "";
  try {
    const backendResponse = await fetch(`${backendUrl()}/${backendPath}${search}`, {
      method,
      cache: "no-store",
      signal: AbortSignal.timeout(BACKEND_TIMEOUT_MS),
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "X-Request-ID": newTraceId(),
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      },
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
    });
    const backendBody: unknown = await backendResponse.json().catch(() => null);
    return NextResponse.json(backendBody, { status: backendResponse.status });
  } catch {
    return envelope("INTERNAL_ERROR", "Backend is unreachable", 502);
  }
}

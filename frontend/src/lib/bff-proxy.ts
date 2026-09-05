import { NextResponse, type NextRequest } from "next/server";

import { BACKEND_TIMEOUT_MS, EXPORT_TIMEOUT_MS, backendUrl, newTraceId } from "@/lib/backend";
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

/**
 * Binary passthrough for file downloads (Excel exports): forwards the
 * session cookie as Bearer and streams the upstream bytes verbatim with
 * the upstream Content-Type/Content-Disposition — no JSON re-parsing, no
 * buffering beyond the response itself. GET only (side-effect free, so no
 * CSRF requirement).
 */
export async function proxyFileToBackend(
  request: NextRequest,
  backendPath: string,
): Promise<NextResponse> {
  const accessToken = request.cookies.get(ACCESS_COOKIE)?.value;
  if (!accessToken) {
    return envelope("AUTHENTICATION_REQUIRED", "No session", 401);
  }

  const search = request.nextUrl.search || "";
  let upstream: Response;
  try {
    upstream = await fetch(`${backendUrl()}/${backendPath}${search}`, {
      cache: "no-store",
      signal: AbortSignal.timeout(EXPORT_TIMEOUT_MS),
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "X-Request-ID": newTraceId(),
      },
    });
  } catch {
    return envelope("INTERNAL_ERROR", "Backend is unreachable", 502);
  }

  if (!upstream.ok || !upstream.body) {
    const body: unknown = await upstream.json().catch(() => null);
    return NextResponse.json(body, { status: upstream.status });
  }

  const headers = new Headers();
  headers.set(
    "Content-Type",
    upstream.headers.get("content-type") ??
      "application/octet-stream",
  );
  const disposition = upstream.headers.get("content-disposition");
  if (disposition) {
    headers.set("Content-Disposition", disposition);
  }
  return new NextResponse(upstream.body, { status: upstream.status, headers });
}

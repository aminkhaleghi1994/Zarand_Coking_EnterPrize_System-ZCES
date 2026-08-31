import { NextResponse, type NextRequest } from "next/server";

import { BACKEND_TIMEOUT_MS, backendUrl, newTraceId } from "@/lib/backend";
import { clearSessionCookies, csrfMatches, REFRESH_COOKIE, CSRF_COOKIE } from "@/lib/session-cookies";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const headerToken = request.headers.get("X-CSRF-Token");
  const cookieToken = request.cookies.get(CSRF_COOKIE)?.value;
  if (!csrfMatches(headerToken, cookieToken)) {
    return NextResponse.json(
      {
        code: "VALIDATION_ERROR",
        message: "Missing or invalid CSRF token",
        details: null,
        trace_id: newTraceId(),
      },
      { status: 403 },
    );
  }

  const refreshToken = request.cookies.get(REFRESH_COOKIE)?.value;
  if (refreshToken) {
    try {
      await fetch(`${backendUrl()}/auth/logout`, {
        method: "POST",
        cache: "no-store",
        signal: AbortSignal.timeout(BACKEND_TIMEOUT_MS),
        headers: { "Content-Type": "application/json", "X-Request-ID": newTraceId() },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
    } catch {
      // logout is idempotent for the browser: cookies are cleared regardless
    }
  }

  const response = NextResponse.json({ success: true }, { status: 200 });
  return clearSessionCookies(response);
}

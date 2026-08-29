import { NextResponse, type NextRequest } from "next/server";

import { BACKEND_TIMEOUT_MS, backendUrl, newTraceId } from "@/lib/backend";
import { MeSchema, TokenPairSchema, type TokenPair } from "@/lib/schemas";
import { applySessionCookies, clearSessionCookies, REFRESH_COOKIE } from "@/lib/session-cookies";

export const dynamic = "force-dynamic";

function localeOf(nextPath: string): string {
  return nextPath.startsWith("/fa") ? "fa" : "en";
}

export async function GET(request: NextRequest) {
  const nextPath = request.nextUrl.searchParams.get("next") || "/";
  const refreshToken = request.cookies.get(REFRESH_COOKIE)?.value;

  if (!refreshToken) {
    const url = request.nextUrl.clone();
    url.pathname = `/${localeOf(nextPath)}/login`;
    url.search = "?expired=1";
    return NextResponse.redirect(url);
  }

  let rotated: TokenPair | null = null;
  try {
    const backendResponse = await fetch(`${backendUrl()}/auth/refresh`, {
      method: "POST",
      cache: "no-store",
      signal: AbortSignal.timeout(BACKEND_TIMEOUT_MS),
      headers: { "Content-Type": "application/json", "X-Request-ID": newTraceId() },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (backendResponse.ok) {
      const parsed = TokenPairSchema.safeParse(await backendResponse.json());
      if (parsed.success) {
        rotated = parsed.data;
      }
    }
  } catch {
    rotated = null;
  }

  if (!rotated) {
    const response = NextResponse.redirect(new URL(`/${localeOf(nextPath)}/login?expired=1`, request.nextUrl));
    return clearSessionCookies(response);
  }

  try {
    const meResponse = await fetch(`${backendUrl()}/auth/me`, {
      cache: "no-store",
      signal: AbortSignal.timeout(BACKEND_TIMEOUT_MS),
      headers: {
        Authorization: `Bearer ${rotated.access_token}`,
        "X-Request-ID": newTraceId(),
      },
    });
    const me = MeSchema.safeParse(await meResponse.json());
    if (!meResponse.ok || !me.success) {
      const response = NextResponse.redirect(
        new URL(`/${localeOf(nextPath)}/login?expired=1`, request.nextUrl),
      );
      return clearSessionCookies(response);
    }
  } catch {
    const response = NextResponse.redirect(
      new URL(`/${localeOf(nextPath)}/login?expired=1`, request.nextUrl),
    );
    return clearSessionCookies(response);
  }

  const response = NextResponse.redirect(new URL(nextPath, request.nextUrl));
  return applySessionCookies(response, {
    accessToken: rotated.access_token,
    accessMaxAge: rotated.access_expires_in,
    refreshToken: rotated.refresh_token,
  });
}

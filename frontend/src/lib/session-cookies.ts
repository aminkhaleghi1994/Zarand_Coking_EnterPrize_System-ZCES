import type { NextResponse } from "next/server";

export const ACCESS_COOKIE = "zces_at";
export const REFRESH_COOKIE = "zces_rt";
export const CSRF_COOKIE = "zces_csrf";

const REFRESH_COOKIE_MAX_AGE = 7 * 24 * 60 * 60;
const CSRF_COOKIE_MAX_AGE = 7 * 24 * 60 * 60;

function secureCookies(): boolean {
  return process.env.COOKIE_SECURE === "true" || process.env.NODE_ENV === "production";
}

const baseCookie = {
  path: "/",
  sameSite: "lax" as const,
  secure: secureCookies(),
  httpOnly: true,
};

export function applySessionCookies(
  response: NextResponse,
  tokens: { accessToken: string; accessMaxAge: number; refreshToken: string },
): NextResponse {
  response.cookies.set({ ...baseCookie, name: ACCESS_COOKIE, value: tokens.accessToken, maxAge: tokens.accessMaxAge });
  response.cookies.set({ ...baseCookie, name: REFRESH_COOKIE, value: tokens.refreshToken, maxAge: REFRESH_COOKIE_MAX_AGE });
  response.cookies.set({
    ...baseCookie,
    name: CSRF_COOKIE,
    httpOnly: false,
    maxAge: CSRF_COOKIE_MAX_AGE,
    value: crypto.randomUUID(),
  });
  return response;
}

export function clearSessionCookies(response: NextResponse): NextResponse {
  for (const name of [ACCESS_COOKIE, REFRESH_COOKIE, CSRF_COOKIE]) {
    response.cookies.set({ ...baseCookie, name, value: "", maxAge: 0 });
  }
  return response;
}

export function csrfMatches(headerValue: string | null, cookieValue: string | undefined): boolean {
  return Boolean(headerValue && cookieValue && headerValue === cookieValue);
}

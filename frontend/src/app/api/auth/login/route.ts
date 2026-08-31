import { NextResponse, type NextRequest } from "next/server";

import { BACKEND_TIMEOUT_MS, backendUrl, newTraceId } from "@/lib/backend";
import {
  LoginInputSchema,
  LoginResponseSchema,
  TokenPairSchema,
} from "@/lib/schemas";
import { applySessionCookies } from "@/lib/session-cookies";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  let raw: unknown;
  try {
    raw = await request.json();
  } catch {
    return NextResponse.json(
      { code: "VALIDATION_ERROR", message: "Invalid JSON body", details: null, trace_id: newTraceId() },
      { status: 422 },
    );
  }

  const parsed = LoginInputSchema.safeParse(raw);
  if (!parsed.success) {
    return NextResponse.json(
      {
        code: "VALIDATION_ERROR",
        message: "Invalid login payload",
        details: null,
        trace_id: newTraceId(),
      },
      { status: 422 },
    );
  }

  try {
    const backendResponse = await fetch(`${backendUrl()}/auth/login`, {
      method: "POST",
      cache: "no-store",
      signal: AbortSignal.timeout(BACKEND_TIMEOUT_MS),
      headers: { "Content-Type": "application/json", "X-Request-ID": newTraceId() },
      body: JSON.stringify(parsed.data),
    });

    if (!backendResponse.ok) {
      const body: unknown = await backendResponse.json().catch(() => null);
      return NextResponse.json(body, { status: backendResponse.status });
    }

    const pair = TokenPairSchema.safeParse(await backendResponse.json());
    if (!pair.success) {
      return NextResponse.json(
        { code: "INTERNAL_ERROR", message: "Unexpected backend response", details: null, trace_id: newTraceId() },
        { status: 502 },
      );
    }

    const sessionView = LoginResponseSchema.parse({
      user: pair.data.user,
      roles: pair.data.roles,
    });
    const response = NextResponse.json(sessionView, { status: 200 });
    return applySessionCookies(response, {
      accessToken: pair.data.access_token,
      accessMaxAge: pair.data.access_expires_in,
      refreshToken: pair.data.refresh_token,
    });
  } catch {
    return NextResponse.json(
      { code: "INTERNAL_ERROR", message: "Backend is unreachable", details: null, trace_id: newTraceId() },
      { status: 502 },
    );
  }
}

import { cookies } from "next/headers";

import { BACKEND_TIMEOUT_MS, backendUrl, newTraceId } from "./backend";
import { ErrorEnvelopeSchema, MeSchema, type Me } from "./schemas";

export type SessionResult =
  | { ok: true; session: Me }
  | { ok: false; code: string; message: string };

export async function getSession(): Promise<SessionResult> {
  const store = await cookies();
  const accessToken = store.get("zces_at")?.value;
  if (!accessToken) {
    return { ok: false, code: "AUTHENTICATION_REQUIRED", message: "No session" };
  }

  try {
    const response = await fetch(`${backendUrl()}/auth/me`, {
      cache: "no-store",
      signal: AbortSignal.timeout(BACKEND_TIMEOUT_MS),
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "X-Request-ID": newTraceId(),
      },
    });
    if (response.ok) {
      const parsed = MeSchema.safeParse(await response.json());
      if (parsed.success) {
        return { ok: true, session: parsed.data };
      }
    }
    const body: unknown = await response.json().catch(() => null);
    const envelope = ErrorEnvelopeSchema.safeParse(body);
    return {
      ok: false,
      code: envelope.success ? envelope.data.code : "AUTHENTICATION_REQUIRED",
      message: envelope.success ? envelope.data.message : "Session invalid",
    };
  } catch {
    return { ok: false, code: "INTERNAL_ERROR", message: "Backend unreachable" };
  }
}

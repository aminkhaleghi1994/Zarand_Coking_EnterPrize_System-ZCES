import { randomUUID } from "crypto";

import { ErrorEnvelopeSchema, HealthStatusSchema } from "./schemas";

const BACKEND_TIMEOUT_MS = 5000;

export type BackendResult<T> =
  | { ok: true; data: T; traceId: string }
  | { ok: false; error: { code: string; message: string; traceId: string } };

function baseUrl(): string {
  const raw = process.env.BACKEND_API_BASE_URL;
  if (!raw) {
    throw new Error("BACKEND_API_BASE_URL is not configured");
  }
  return raw.replace(/\/+$/, "");
}

async function parseEnvelope(response: Response): Promise<{ code: string; message: string }> {
  try {
    const body: unknown = await response.json();
    const parsed = ErrorEnvelopeSchema.safeParse(body);
    if (parsed.success) {
      return { code: parsed.data.code, message: parsed.data.message };
    }
  } catch {
    // fall through to generic mapping
  }
  return {
    code: response.status === 404 ? "RESOURCE_NOT_FOUND" : "INTERNAL_ERROR",
    message: "Unexpected backend response",
  };
}

export async function backendHealth(): Promise<
  BackendResult<import("./schemas").HealthStatus>
> {
  let traceId = "";
  try {
    const response = await fetch(`${baseUrl()}/healthz`, {
      cache: "no-store",
      signal: AbortSignal.timeout(BACKEND_TIMEOUT_MS),
      headers: { "X-Request-ID": randomUUID() },
    });
    traceId = response.headers.get("X-Request-ID") ?? randomUUID();
    if (!response.ok) {
      const mapped = await parseEnvelope(response);
      return { ok: false, error: { ...mapped, traceId } };
    }
    const body: unknown = await response.json();
    const parsed = HealthStatusSchema.safeParse(body);
    if (!parsed.success) {
      return {
        ok: false,
        error: { code: "INTERNAL_ERROR", message: "Unexpected backend response", traceId },
      };
    }
    return { ok: true, data: parsed.data, traceId };
  } catch {
    return {
      ok: false,
      error: {
        code: "INTERNAL_ERROR",
        message: "Backend is unreachable",
        traceId: traceId || randomUUID(),
      },
    };
  }
}

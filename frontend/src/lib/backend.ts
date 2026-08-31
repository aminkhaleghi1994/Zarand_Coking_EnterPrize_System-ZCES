import { randomUUID } from "crypto";

export function backendUrl(): string {
  const raw = process.env.BACKEND_API_BASE_URL;
  if (!raw) {
    throw new Error("BACKEND_API_BASE_URL is not configured");
  }
  return raw.replace(/\/+$/, "");
}

export const BACKEND_TIMEOUT_MS = 5000;

export function newTraceId(): string {
  return randomUUID();
}

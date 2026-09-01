import type { NextRequest } from "next/server";

import { proxyToBackend } from "@/lib/bff-proxy";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  return proxyToBackend(request, "GET", "loan/requests");
}

export async function POST(request: NextRequest) {
  const body: unknown = await request.json().catch(() => null);
  return proxyToBackend(request, "POST", "loan/requests", body);
}

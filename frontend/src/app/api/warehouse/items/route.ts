import type { NextRequest } from "next/server";

import { proxyToBackend } from "@/lib/bff-proxy";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  return proxyToBackend(request, "GET", "warehouse/items");
}

export async function POST(request: NextRequest) {
  const body: unknown = await request.json().catch(() => null);
  return proxyToBackend(request, "POST", "warehouse/items", body);
}

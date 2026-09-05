import type { NextRequest } from "next/server";

import { proxyToBackend } from "@/lib/bff-proxy";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  return proxyToBackend(request, "GET", `warehouse/warehouses/${id}/shelves`);
}

export async function POST(request: NextRequest, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  const body: unknown = await request.json().catch(() => null);
  return proxyToBackend(request, "POST", `warehouse/warehouses/${id}/shelves`, body);
}

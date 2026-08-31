import type { NextRequest } from "next/server";

import { proxyToBackend } from "@/lib/bff-proxy";

export const dynamic = "force-dynamic";

type Params = { params: Promise<{ id: string }> };

export async function GET(request: NextRequest, { params }: Params) {
  const { id } = await params;
  return proxyToBackend(request, "GET", `users/${id}/roles`);
}

export async function POST(request: NextRequest, { params }: Params) {
  const { id } = await params;
  const body: unknown = await request.json().catch(() => null);
  return proxyToBackend(request, "POST", `users/${id}/roles`, body);
}

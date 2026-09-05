import type { NextRequest } from "next/server";

import { proxyToBackend } from "@/lib/bff-proxy";

export const dynamic = "force-dynamic";

export async function PATCH(
  request: NextRequest,
  context: { params: Promise<{ key: string }> },
) {
  const { key } = await context.params;
  const body: unknown = await request.json().catch(() => null);
  return proxyToBackend(request, "PATCH", `settings/${key}`, body);
}

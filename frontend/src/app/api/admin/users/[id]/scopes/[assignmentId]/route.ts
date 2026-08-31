import type { NextRequest } from "next/server";

import { proxyToBackend } from "@/lib/bff-proxy";

export const dynamic = "force-dynamic";

type Params = { params: Promise<{ id: string; assignmentId: string }> };

export async function DELETE(request: NextRequest, { params }: Params) {
  const { id, assignmentId } = await params;
  return proxyToBackend(request, "DELETE", `users/${id}/scopes/${assignmentId}`);
}

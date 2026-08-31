import type { NextRequest } from "next/server";

import { proxyToBackend } from "@/lib/bff-proxy";

export const dynamic = "force-dynamic";

type Params = { params: Promise<{ id: string; roleId: string }> };

export async function DELETE(request: NextRequest, { params }: Params) {
  const { id, roleId } = await params;
  return proxyToBackend(request, "DELETE", `users/${id}/roles/${roleId}`);
}

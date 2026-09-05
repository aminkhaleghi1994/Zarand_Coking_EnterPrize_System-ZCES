import type { NextRequest } from "next/server";

import { proxyFileToBackend } from "@/lib/bff-proxy";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  return proxyFileToBackend(request, "reports/export/excel");
}

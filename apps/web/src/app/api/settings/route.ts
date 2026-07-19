import { proxyJsonResponse } from "../_lib/proxy";
import { type NextRequest } from "next/server";

/**
 * GET /api/settings → GET /settings (no /api/v1 prefix on backend)
 * PUT /api/settings → PUT /settings
 */
export async function GET() {
  return proxyJsonResponse("/settings", undefined, false);
}

export async function POST(request: NextRequest) {
  const body = await request.text();
  return proxyJsonResponse("/settings", { method: "PUT", body }, false);
}

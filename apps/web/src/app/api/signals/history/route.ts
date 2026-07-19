import { proxyJsonResponse } from "../../_lib/proxy";
import { type NextRequest } from "next/server";

/**
 * GET /api/signals/history → GET /api/v1/signals/history
 */
export async function GET(request: NextRequest) {
  const qs = request.nextUrl.searchParams.toString();
  return proxyJsonResponse(`/signals/history${qs ? `?${qs}` : ""}`);
}

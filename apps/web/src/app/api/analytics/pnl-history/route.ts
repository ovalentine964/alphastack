import { proxyJsonResponse } from "../../_lib/proxy";
import { type NextRequest } from "next/server";

/**
 * GET /api/analytics/pnl-history → GET /api/v1/analytics/pnl-history
 */
export async function GET(request: NextRequest) {
  const qs = request.nextUrl.searchParams.toString();
  return proxyJsonResponse(`/analytics/pnl-history${qs ? `?${qs}` : ""}`);
}

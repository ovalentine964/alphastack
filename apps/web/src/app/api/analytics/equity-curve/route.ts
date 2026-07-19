import { proxyJsonResponse } from "../../_lib/proxy";
import { type NextRequest } from "next/server";

/**
 * GET /api/analytics/equity-curve → GET /api/v1/analytics/equity-curve
 */
export async function GET(request: NextRequest) {
  const qs = request.nextUrl.searchParams.toString();
  return proxyJsonResponse(`/analytics/equity-curve${qs ? `?${qs}` : ""}`);
}

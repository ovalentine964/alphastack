import { proxyJsonResponse } from "../../_lib/proxy";

/**
 * GET /api/analytics/performance → GET /api/v1/analytics/performance
 */
export async function GET() {
  return proxyJsonResponse("/analytics/performance");
}

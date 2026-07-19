import { proxyJsonResponse } from "../../_lib/proxy";

/**
 * GET /api/analytics/risk → GET /api/v1/analytics/risk
 */
export async function GET() {
  return proxyJsonResponse("/analytics/risk");
}

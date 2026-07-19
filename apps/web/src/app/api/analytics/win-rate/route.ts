import { proxyJsonResponse } from "../../_lib/proxy";

/**
 * GET /api/analytics/win-rate → GET /api/v1/analytics/win-rate
 */
export async function GET() {
  return proxyJsonResponse("/analytics/win-rate");
}

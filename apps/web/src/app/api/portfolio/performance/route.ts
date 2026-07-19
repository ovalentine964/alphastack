import { proxyJsonResponse } from "../../_lib/proxy";

/**
 * GET /api/portfolio/performance → GET /api/v1/portfolio/performance
 */
export async function GET() {
  return proxyJsonResponse("/portfolio/performance");
}

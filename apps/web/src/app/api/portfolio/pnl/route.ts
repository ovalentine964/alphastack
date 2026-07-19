import { proxyJsonResponse } from "../../_lib/proxy";

/**
 * GET /api/portfolio/pnl → GET /api/v1/portfolio/pnl
 */
export async function GET() {
  return proxyJsonResponse("/portfolio/pnl");
}

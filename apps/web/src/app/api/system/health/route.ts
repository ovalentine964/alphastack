import { proxyJsonResponse } from "../../_lib/proxy";

/**
 * GET /api/system/health → GET /health (no /api/v1 prefix on backend)
 */
export async function GET() {
  return proxyJsonResponse("/health", undefined, false);
}

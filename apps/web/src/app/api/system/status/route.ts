import { proxyJsonResponse } from "../../_lib/proxy";

/**
 * GET /api/system/status → GET /status (no /api/v1 prefix on backend)
 */
export async function GET() {
  return proxyJsonResponse("/status", undefined, false);
}

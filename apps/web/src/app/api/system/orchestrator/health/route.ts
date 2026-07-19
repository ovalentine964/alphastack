import { proxyJsonResponse } from "../../../_lib/proxy";

/**
 * GET /api/system/orchestrator/health → GET /orchestrator/health
 */
export async function GET() {
  return proxyJsonResponse("/orchestrator/health", undefined, false);
}

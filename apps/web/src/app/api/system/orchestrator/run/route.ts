import { proxyJsonResponse } from "../../../_lib/proxy";
import { type NextRequest } from "next/server";

/**
 * POST /api/system/orchestrator/run → POST /orchestrator/run
 */
export async function POST(request: NextRequest) {
  const body = await request.text();
  return proxyJsonResponse(
    "/orchestrator/run",
    { method: "POST", body },
    false
  );
}

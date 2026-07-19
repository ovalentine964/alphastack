import { proxyJsonResponse } from "../../_lib/proxy";
import { type NextRequest } from "next/server";

/**
 * GET /api/trades/[id] → GET /api/v1/trades/[id]
 */
export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return proxyJsonResponse(`/trades/${id}`);
}

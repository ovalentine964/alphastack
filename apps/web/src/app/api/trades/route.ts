import { proxyJsonResponse } from "../_lib/proxy";
import { type NextRequest } from "next/server";

/**
 * GET /api/trades → GET /api/v1/trades
 * POST /api/trades → POST /api/v1/trades
 */
export async function GET(request: NextRequest) {
  const qs = request.nextUrl.searchParams.toString();
  return proxyJsonResponse(`/trades${qs ? `?${qs}` : ""}`);
}

export async function POST(request: NextRequest) {
  const body = await request.text();
  return proxyJsonResponse("/trades", {
    method: "POST",
    body,
  });
}

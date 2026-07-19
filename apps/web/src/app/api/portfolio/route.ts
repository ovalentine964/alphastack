import { proxyJsonResponse } from "../_lib/proxy";
import { type NextRequest } from "next/server";

/**
 * GET /api/portfolio → GET /api/v1/portfolio
 * Returns list of open positions.
 */
export async function GET() {
  return proxyJsonResponse("/portfolio");
}

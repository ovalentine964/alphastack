import { proxyJsonResponse } from "../../../_lib/proxy";
import { type NextRequest } from "next/server";

/**
 * PUT /api/trades/[id]/close → PUT /api/v1/trades/[id]/close
 */
export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const qs = request.nextUrl.searchParams.toString();
  return proxyJsonResponse(`/trades/${id}/close${qs ? `?${qs}` : ""}`, {
    method: "PUT",
  });
}

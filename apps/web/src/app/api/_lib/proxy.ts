/**
 * Shared proxy utility for forwarding requests to the Python backend.
 *
 * Backend runs at BACKEND_URL (default: http://localhost:8000).
 * Routes are prefixed with /api/v1 on the backend for most endpoints.
 */

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";
const API_PREFIX = "/api/v1";

/**
 * Proxy a request to the Python backend.
 *
 * @param path - The backend path (without the /api/v1 prefix), e.g. "/portfolio"
 * @param options - Fetch options to forward
 * @param useApiPrefix - Whether to prepend /api/v1 (default: true)
 */
export async function proxyRequest(
  path: string,
  options?: RequestInit,
  useApiPrefix = true
): Promise<Response> {
  const prefix = useApiPrefix ? API_PREFIX : "";
  const url = `${BACKEND_URL}${prefix}${path}`;

  const headers = new Headers(options?.headers);
  if (!headers.has("Content-Type") && options?.body) {
    headers.set("Content-Type", "application/json");
  }

  return fetch(url, {
    ...options,
    headers,
  });
}

/**
 * Create a JSON response from a backend proxy result.
 */
export async function proxyJsonResponse(
  path: string,
  options?: RequestInit,
  useApiPrefix = true
): Promise<Response> {
  const res = await proxyRequest(path, options, useApiPrefix);

  const body = await res.text();
  return new Response(body, {
    status: res.status,
    headers: {
      "Content-Type": "application/json",
    },
  });
}

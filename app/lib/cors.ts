/**
 * Validates that the request is from the same origin
 * Throws a Response with 403 if cross-origin
 */
export function validateSameOrigin(request: Request): void {
  const url = new URL(request.url);
  const origin = request.headers.get("origin");
  const requestOrigin = `${url.protocol}//${url.host}`;

  // If there's an origin header and it doesn't match, reject
  if (origin && origin !== requestOrigin) {
    throw new Response("Forbidden: Cross-origin requests are not allowed", {
      status: 403,
      headers: {
        "Access-Control-Allow-Origin": "null",
      },
    });
  }
}

/**
 * Handles OPTIONS preflight requests
 */
export function handleOptionsRequest(request: Request): Response | null {
  if (request.method === "OPTIONS") {
    const url = new URL(request.url);
    const origin = request.headers.get("origin");
    const requestOrigin = `${url.protocol}//${url.host}`;
    const isSameOrigin = !origin || origin === requestOrigin;

    return new Response(null, {
      status: 204,
      headers: {
        "Access-Control-Allow-Origin": isSameOrigin ? requestOrigin : "null",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Max-Age": "0",
      },
    });
  }
  return null;
}


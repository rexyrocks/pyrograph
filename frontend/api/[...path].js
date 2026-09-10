const ROUTES = new Map([
  ['health', new Set(['GET'])],
  ['demographics/wards', new Set(['GET'])],
  ['risk/assess', new Set(['POST'])],
]);

const MAX_BODY_BYTES = 512 * 1024;

export default async function handler(request, response) {
  const url = new URL(request.url, `http://${request.headers.host}`);
  const path = url.pathname.replace(/^\/api\//, '');
  const methods = ROUTES.get(path);

  response.setHeader('Cache-Control', 'no-store');
  response.setHeader('X-Content-Type-Options', 'nosniff');

  if (!methods || !methods.has(request.method)) {
    return response.status(404).json({ detail: 'Not found' });
  }

  const upstreamUrl = process.env.RAILWAY_API_URL?.replace(/\/$/, '');
  const apiKey = process.env.RAILWAY_API_KEY;
  if (!upstreamUrl || !apiKey) {
    return response.status(503).json({ detail: 'Prediction service unavailable' });
  }

  let body;
  if (request.method === 'POST') {
    body = JSON.stringify(request.body ?? {});
    if (Buffer.byteLength(body, 'utf8') > MAX_BODY_BYTES) {
      return response.status(413).json({ detail: 'Request too large' });
    }
  }

  try {
    const upstream = await fetch(`${upstreamUrl}/${path}`, {
      method: request.method,
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': apiKey,
      },
      body,
      signal: AbortSignal.timeout(20_000),
    });
    const payload = await upstream.text();
    response.status(upstream.status);
    response.setHeader(
      'Content-Type',
      upstream.headers.get('content-type') ?? 'application/json',
    );
    if (path === 'health' && upstream.ok) {
      response.setHeader('Cache-Control', 's-maxage=60, stale-while-revalidate=300');
    }
    return response.send(payload);
  } catch {
    return response.status(502).json({ detail: 'Prediction service unavailable' });
  }
}

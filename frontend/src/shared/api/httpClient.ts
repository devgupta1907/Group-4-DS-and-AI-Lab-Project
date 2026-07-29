/**
 * The single HTTP entry point. Nothing else in the app calls `fetch`
 * (AGENTS.md rule 1, enforced by `no-restricted-globals` in eslint.config.js).
 */
import { ApiError, toApiError } from './ApiError';

const BASE_URL = '/api';

/** Dev auth header. Google SSO replaces this without touching any caller. */
function authHeaders(): HeadersInit {
  return { 'X-Dev-User-Id': 'dev-user' };
}

type ErrorBody = { code?: string; message?: string; detail?: string };

async function readError(response: Response): Promise<ApiError> {
  let body: ErrorBody = {};
  try {
    body = (await response.json()) as ErrorBody;
  } catch {
    // A non-JSON error body is still an error; fall through to the default.
  }
  return new ApiError(
    body.code ?? 'http_error',
    body.message ?? body.detail ?? `Request failed (${response.status}).`,
    response.status,
  );
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers: { ...authHeaders(), ...init.headers },
    });
  } catch (cause) {
    throw toApiError(cause);
  }

  if (!response.ok) throw await readError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/**
 * POSTs a file and returns the raw streaming response.
 *
 * `EventSource` cannot issue a multipart POST, so an SSE upload has to go
 * through `fetch` and be read off the body stream — see `sseClient.ts`.
 */
export async function postFileForStream(
  path: string,
  file: File,
  signal?: AbortSignal,
): Promise<Response> {
  const body = new FormData();
  body.append('file', file);

  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      method: 'POST',
      headers: { ...authHeaders(), Accept: 'text/event-stream' },
      body,
      signal,
    });
  } catch (cause) {
    throw toApiError(cause);
  }

  if (!response.ok) throw await readError(response);
  if (!response.body) throw ApiError.network();
  return response;
}

/**
 * A failure the UI can branch on.
 *
 * The backend gives every failure a stable `code`; the UI switches on that and
 * never on message text, so wording changes are not breaking changes.
 */
export class ApiError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(code: string, message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.status = status;
  }

  static network(): ApiError {
    return new ApiError(
      'network_unavailable',
      'Could not reach the server. Check that the backend is running.',
      0,
    );
  }
}

/** Narrows an unknown catch value without resorting to `any`. */
export function toApiError(cause: unknown): ApiError {
  if (cause instanceof ApiError) return cause;
  if (cause instanceof DOMException && cause.name === 'AbortError') {
    return new ApiError('cancelled', 'Request cancelled.', 0);
  }
  return ApiError.network();
}

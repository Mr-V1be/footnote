import type { Problem } from "./types";

/** A failed API call with the server's stable error code. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    detail?: string | null,
  ) {
    super(detail ?? code);
    this.name = "ApiError";
  }

  get isUnauthenticated(): boolean {
    return this.status === 401;
  }

  get isForbidden(): boolean {
    return this.status === 403;
  }

  get isNotFound(): boolean {
    return this.status === 404;
  }
}

function isProblem(value: unknown): value is Problem {
  return typeof value === "object" && value !== null && "code" in value && "status" in value;
}

/** Turns an openapi-fetch result into data or a typed error. */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.data !== undefined) return result.data;
  const problem = isProblem(result.error) ? result.error : null;
  throw new ApiError(result.response.status, problem?.code ?? "unexpected_error", problem?.detail);
}

/** For a call that answers without a body (204): only a failure carries information. */
export function unwrapEmpty(result: { error?: unknown; response: Response }): void {
  if (result.response.ok) return;
  unwrap({ error: result.error, response: result.response });
}

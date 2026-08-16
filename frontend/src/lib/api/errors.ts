/**
 * Standardized API Error Hierarchy for AI Research Assistant.
 * Distinguishes network failures, HTTP status codes, and server errors
 * without leaking raw connection strings or backend stack traces.
 */

export class ApiError extends Error {
  public readonly status: number;
  public readonly code: string;
  public readonly details: unknown;
  public readonly isNetworkError: boolean;

  constructor(
    message: string,
    status = 500,
    code = "API_ERROR",
    details: unknown = null,
    isNetworkError = false
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
    this.isNetworkError = isNetworkError;
    Object.setPrototypeOf(this, new.target.prototype);
  }

  /**
   * Factory method to build a specialized ApiError from an HTTP response and parsed payload.
   */
  public static fromResponse(status: number, data: unknown, statusText?: string): ApiError {
    let message = statusText || `Request failed with status ${status}`;
    let code = "API_ERROR";
    let details: unknown = null;

    if (data && typeof data === "object") {
      const payload = data as Record<string, unknown>;

      // Standardized AppException JSON envelope from backend: { error: { code, message, details } }
      if (payload.error && typeof payload.error === "object") {
        const errObj = payload.error as Record<string, unknown>;
        if (typeof errObj.message === "string") message = errObj.message;
        if (typeof errObj.code === "string") code = errObj.code;
        if (errObj.details !== undefined) details = errObj.details;
      } else if (typeof payload.message === "string") {
        message = payload.message;
      } else if (typeof payload.detail === "string") {
        message = payload.detail;
      } else if (Array.isArray(payload.detail) && payload.detail.length > 0) {
        // FastAPI / Pydantic validation error array
        code = "VALIDATION_ERROR";
        message = payload.detail
          .map((d: Record<string, unknown>) => `${d.loc ? (d.loc as string[]).join(".") : "field"}: ${d.msg || "invalid"}`)
          .join("; ");
        details = payload.detail;
      }
    }

    switch (status) {
      case 400:
        return new BadRequestError(message, details, code);
      case 401:
        return new UnauthorizedError(message, details, code);
      case 403:
        return new ForbiddenError(message, details, code);
      case 404:
        return new NotFoundError(message, details, code);
      case 422:
        return new ValidationError(message, details, code);
      case 500:
      case 502:
      case 503:
      case 504:
        return new ServerError(message, status, details, code);
      default:
        return new ApiError(message, status, code, details);
    }
  }
}

export class NetworkError extends ApiError {
  constructor(
    message = "Unable to connect to the research assistant backend. Please verify that the API server is running."
  ) {
    super(message, 0, "NETWORK_ERROR", null, true);
    this.name = "NetworkError";
  }
}

export class BadRequestError extends ApiError {
  constructor(message = "The request was invalid or malformed.", details: unknown = null, code = "BAD_REQUEST") {
    super(message, 400, code, details);
    this.name = "BadRequestError";
  }
}

export class UnauthorizedError extends ApiError {
  constructor(message = "Authentication credentials missing or invalid.", details: unknown = null, code = "UNAUTHORIZED") {
    super(message, 401, code, details);
    this.name = "UnauthorizedError";
  }
}

export class ForbiddenError extends ApiError {
  constructor(message = "You do not have permission to access this resource.", details: unknown = null, code = "FORBIDDEN") {
    super(message, 403, code, details);
    this.name = "ForbiddenError";
  }
}

export class NotFoundError extends ApiError {
  constructor(message = "The requested resource was not found.", details: unknown = null, code = "NOT_FOUND") {
    super(message, 404, code, details);
    this.name = "NotFoundError";
  }
}

export class ValidationError extends ApiError {
  constructor(message = "Validation failed for the submitted data.", details: unknown = null, code = "VALIDATION_ERROR") {
    super(message, 422, code, details);
    this.name = "ValidationError";
  }
}

export class ServerError extends ApiError {
  constructor(
    message = "An internal server error occurred in the backend service.",
    status = 500,
    details: unknown = null,
    code = "INTERNAL_SERVER_ERROR"
  ) {
    super(message, status, code, details);
    this.name = "ServerError";
  }
}

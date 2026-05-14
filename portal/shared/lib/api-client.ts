import { ApiError } from "@shared/types/api";
import { isMockEnabled, mockResponse } from "./mock-data";

export class ApiClientError extends Error {
  public readonly code: string;
  public readonly correlationId: string;
  public readonly status: number;
  public readonly field?: string;

  constructor(
    message: string,
    code: string,
    correlationId: string,
    status: number,
    field?: string
  ) {
    super(message);
    this.name = "ApiClientError";
    this.code = code;
    this.correlationId = correlationId;
    this.status = status;
    this.field = field;
  }
}

interface FetchOptions extends RequestInit {
  retries?: number;
  retryDelayMs?: number;
}

type TokenProvider = () => Promise<string | null | undefined>;
type TenantProvider = () => Promise<string | null | undefined>;

let _tokenProvider: TokenProvider | null = null;
let _tenantProvider: TenantProvider | null = null;
let _refreshCallback: (() => Promise<void>) | null = null;

export function configureApiClient(opts: {
  tokenProvider: TokenProvider;
  tenantProvider?: TenantProvider;
  onUnauthorized?: () => Promise<void>;
}): void {
  _tokenProvider = opts.tokenProvider;
  _tenantProvider = opts.tenantProvider ?? null;
  _refreshCallback = opts.onUnauthorized ?? null;
}

async function getAuthHeaders(): Promise<Record<string, string>> {
  const headers: Record<string, string> = {};
  if (_tokenProvider) {
    const token = await _tokenProvider();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
  }
  // Every backend route validates x-tenant-id as a required UUID header.
  // Without it the request fails at FastAPI validation (422) before the
  // handler runs — which presents to the user as "no data, no error."
  // Resolve from the configured provider (typically the NextAuth session's
  // tenant_id), else fall back to NEXT_PUBLIC_DEFAULT_TENANT_ID for unauthed
  // calls during early page load.
  if (_tenantProvider) {
    const tenant = await _tenantProvider();
    if (tenant) {
      headers["x-tenant-id"] = tenant;
    }
  }
  if (!headers["x-tenant-id"]) {
    const fallback = process.env.NEXT_PUBLIC_DEFAULT_TENANT_ID;
    if (fallback) {
      headers["x-tenant-id"] = fallback;
    }
  }
  return headers;
}

async function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function fetchWithRetry(
  url: string,
  options: FetchOptions = {}
): Promise<Response> {
  const { retries = 3, retryDelayMs = 500, ...fetchOpts } = options;
  const authHeaders = await getAuthHeaders();

  const mergedOptions: RequestInit = {
    ...fetchOpts,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
      ...(fetchOpts.headers as Record<string, string> | undefined),
    },
  };

  let lastError: Error | null = null;

  for (let attempt = 0; attempt < retries; attempt++) {
    try {
      const response = await fetch(url, mergedOptions);

      if (response.status === 401) {
        if (_refreshCallback && attempt === 0) {
          await _refreshCallback();
          const newAuthHeaders = await getAuthHeaders();
          mergedOptions.headers = {
            ...mergedOptions.headers,
            ...newAuthHeaders,
          };
          continue;
        }
      }

      // Retry on 5xx errors with exponential backoff
      if (response.status >= 500 && attempt < retries - 1) {
        await sleep(retryDelayMs * Math.pow(2, attempt));
        continue;
      }

      return response;
    } catch (err) {
      lastError = err instanceof Error ? err : new Error(String(err));
      if (attempt < retries - 1) {
        await sleep(retryDelayMs * Math.pow(2, attempt));
      }
    }
  }

  throw lastError ?? new Error("Fetch failed after retries");
}

async function parseApiError(response: Response): Promise<ApiClientError> {
  let body: Partial<ApiError> | null = null;
  try {
    body = (await response.json()) as Partial<ApiError>;
  } catch {
    // could not parse JSON
  }

  const errorPayload = body?.error;
  return new ApiClientError(
    errorPayload?.message ?? `HTTP ${response.status}`,
    errorPayload?.code ?? `HTTP_${response.status}`,
    errorPayload?.correlation_id ?? "",
    response.status,
    errorPayload?.field
  );
}

export async function apiGet<T>(url: string, options?: FetchOptions): Promise<T> {
  if (isMockEnabled()) return mockResponse<T>("GET", url);
  const response = await fetchWithRetry(url, { ...options, method: "GET" });
  if (!response.ok) {
    throw await parseApiError(response);
  }
  return response.json() as Promise<T>;
}

export async function apiPost<T>(
  url: string,
  body: unknown,
  options?: FetchOptions
): Promise<T> {
  if (isMockEnabled()) return mockResponse<T>("POST", url, body);
  const response = await fetchWithRetry(url, {
    ...options,
    method: "POST",
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw await parseApiError(response);
  }
  return response.json() as Promise<T>;
}

export async function apiPut<T>(
  url: string,
  body: unknown,
  options?: FetchOptions
): Promise<T> {
  if (isMockEnabled()) return mockResponse<T>("PUT", url, body);
  const response = await fetchWithRetry(url, {
    ...options,
    method: "PUT",
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw await parseApiError(response);
  }
  return response.json() as Promise<T>;
}

export async function apiPatch<T>(
  url: string,
  body: unknown,
  options?: FetchOptions
): Promise<T> {
  if (isMockEnabled()) return mockResponse<T>("PATCH", url, body);
  const response = await fetchWithRetry(url, {
    ...options,
    method: "PATCH",
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw await parseApiError(response);
  }
  return response.json() as Promise<T>;
}

export async function apiDelete<T = void>(
  url: string,
  options?: FetchOptions
): Promise<T> {
  if (isMockEnabled()) return mockResponse<T>("DELETE", url);
  const response = await fetchWithRetry(url, { ...options, method: "DELETE" });
  if (!response.ok) {
    throw await parseApiError(response);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

/**
 * Build a URL with query parameters, filtering out null/undefined values.
 */
export function buildUrl(
  base: string,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  params?: Record<string, any> | null
): string {
  if (!params) return base;
  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== "") {
      searchParams.set(key, String(value));
    }
  }
  const qs = searchParams.toString();
  return qs ? `${base}?${qs}` : base;
}

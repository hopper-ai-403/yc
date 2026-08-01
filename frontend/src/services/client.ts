import axios, {
  AxiosError,
  AxiosInstance,
  AxiosRequestConfig,
  InternalAxiosRequestConfig,
} from "axios";

import { API_URL } from "@/lib/env";
import type { ErrorEnvelope } from "@/types/api";

/** Normalized API failure surfaced to callers and query error states. */
export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details: Record<string, unknown>;
  readonly requestId: string | null;

  constructor(args: {
    message: string;
    code: string;
    status: number;
    details?: Record<string, unknown>;
    requestId?: string | null;
  }) {
    super(args.message);
    this.name = "ApiError";
    this.code = args.code;
    this.status = args.status;
    this.details = args.details ?? {};
    this.requestId = args.requestId ?? null;
  }
}

export function generateRequestId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `req-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

function isErrorEnvelope(payload: unknown): payload is ErrorEnvelope {
  return (
    typeof payload === "object" &&
    payload !== null &&
    (payload as { success?: unknown }).success === false &&
    typeof (payload as { error?: { code?: unknown } }).error?.code === "string"
  );
}

function onRequest(
  config: InternalAxiosRequestConfig,
): InternalAxiosRequestConfig {
  config.headers.set("X-Request-Id", generateRequestId());
  config.headers.set("Accept", "application/json");
  return config;
}

/** Unwrap the canonical success envelope; SDK methods return `data` only. */
function unwrap<T>(payload: unknown): T {
  if (isErrorEnvelope(payload)) {
    throw new ApiError({
      message: payload.error.message,
      code: payload.error.code,
      status: 200,
      details: payload.error.details,
    });
  }
  const envelope = payload as { data?: unknown };
  if (envelope && typeof envelope === "object" && "data" in envelope) {
    return envelope.data as T;
  }
  return payload as T;
}

function onError(error: AxiosError): Promise<never> {
  const status = error.response?.status ?? 0;
  const payload = error.response?.data;
  const requestId =
    (error.response?.headers?.["x-request-id"] as string | undefined) ?? null;

  if (isErrorEnvelope(payload)) {
    return Promise.reject(
      new ApiError({
        message: payload.error.message,
        code: payload.error.code,
        status,
        details: payload.error.details,
        requestId,
      }),
    );
  }

  return Promise.reject(
    new ApiError({
      message: error.message || "Network request failed",
      code: status === 0 ? "NETWORK_ERROR" : "HTTP_ERROR",
      status,
      requestId,
    }),
  );
}

export function createApiClient(): AxiosInstance {
  const client = axios.create({
    baseURL: `${API_URL}/api/v1`,
    timeout: 30_000,
    withCredentials: false,
  });

  client.interceptors.request.use(onRequest);
  client.interceptors.response.use(
    (response) => {
      response.data = unwrap(response.data);
      return response;
    },
    onError,
  );

  return client;
}

/** Shared singleton client for all feature SDKs. */
export const apiClient = createApiClient();

export async function get<T>(
  url: string,
  config?: AxiosRequestConfig,
): Promise<T> {
  const response = await apiClient.get<T>(url, config);
  return response.data;
}

export async function post<T>(
  url: string,
  body?: unknown,
  config?: AxiosRequestConfig,
): Promise<T> {
  const response = await apiClient.post<T>(url, body, config);
  return response.data;
}

export async function del<T>(
  url: string,
  config?: AxiosRequestConfig,
): Promise<T> {
  const response = await apiClient.delete<T>(url, config);
  return response.data;
}

/** Raw client for endpoints that bypass the envelope (file downloads). */
export function rawClient(): AxiosInstance {
  const client = axios.create({ baseURL: `${API_URL}/api/v1`, timeout: 60_000 });
  client.interceptors.request.use(onRequest);
  return client;
}

/** Client rooted at the API origin (for /health endpoints outside /api/v1). */
export const rootClient = (() => {
  const client = axios.create({ baseURL: API_URL, timeout: 15_000 });
  client.interceptors.request.use(onRequest);
  client.interceptors.response.use(
    (response) => {
      response.data = unwrap(response.data);
      return response;
    },
    onError,
  );
  return client;
})();

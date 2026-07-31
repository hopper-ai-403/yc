/** Canonical API envelope shared by every endpoint. */

export interface SuccessEnvelope<T> {
  success: true;
  message: string;
  data: T;
}

export interface ErrorBody {
  code: string;
  message: string;
  details: Record<string, unknown>;
}

export interface ErrorEnvelope {
  success: false;
  error: ErrorBody;
}

export type ApiEnvelope<T> = SuccessEnvelope<T> | ErrorEnvelope;

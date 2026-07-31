const FALLBACK_API_URL = "http://localhost:8000";

/** Resolved backend base URL (no trailing slash). */
export const API_URL = (
  process.env.NEXT_PUBLIC_API_URL ?? FALLBACK_API_URL
).replace(/\/+$/, "");

export const IS_BROWSER = typeof window !== "undefined";

export const APP_NAME = "Audio Intelligence Studio";

export const ROUTES = {
  dashboard: "/",
  upload: "/upload",
  batches: "/batches",
  batchDetail: (id: string) => `/batches/${id}`,
  audioDetail: (id: string) => `/audio/${id}`,
  benchmark: "/benchmark",
  system: "/system",
} as const;

export const QUERY_STALE_TIME_MS = 15_000;
export const QUERY_GC_TIME_MS = 5 * 60_000;
export const JOB_PROGRESS_REFETCH_MS = 2_000;
export const SYSTEM_METRICS_REFETCH_MS = 15_000;

export const ACCEPTED_AUDIO_EXTENSIONS = [".wav", ".mp3", ".ogg"] as const;
export const ACCEPTED_ARCHIVE_EXTENSIONS = [".zip"] as const;

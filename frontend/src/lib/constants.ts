export const APP_NAME = "Audio Intelligence Studio";

export const ROUTES = {
  dashboard: "/",
  upload: "/upload",
  batches: "/batches",
  batchDetail: (id: string) => `/batches/${id}`,
  audioDetail: (id: string) => `/audio/${id}`,
  benchmark: "/benchmark",
  evaluation: "/evaluation",
  system: "/system",
} as const;

/** Assessment fields used by exports and evaluation comparisons. */
export const ASSESSMENT_FIELDS = [
  "emotional_tone",
  "emotional_intensity",
  "background_noise_present",
  "background_noise_type",
  "background_noise_severity",
  "audio_quality",
  "speaker_overlap_present",
  "long_silence_present",
  "confidence",
] as const;

export const QUERY_STALE_TIME_MS = 15_000;
export const QUERY_GC_TIME_MS = 5 * 60_000;
export const JOB_PROGRESS_REFETCH_MS = 2_000;
export const SYSTEM_METRICS_REFETCH_MS = 15_000;

export const ACCEPTED_AUDIO_EXTENSIONS = [".wav", ".mp3", ".ogg"] as const;
export const ACCEPTED_ARCHIVE_EXTENSIONS = [".zip"] as const;

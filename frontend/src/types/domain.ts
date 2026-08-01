/** Domain models mirroring the backend API schemas exactly. */

export type BatchStatus =
  | "UPLOADED"
  | "VALIDATED"
  | "QUEUED"
  | "PROCESSING"
  | "COMPLETED"
  | "FAILED";

export type AudioStatus =
  | "UPLOADED"
  | "VALIDATED"
  | "QUEUED"
  | "PROCESSING"
  | "PROCESSED"
  | "COMPLETED"
  | "FAILED";

export type JobStatus =
  | "PENDING"
  | "QUEUED"
  | "RUNNING"
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED";

export type EmotionTone =
  | "NEUTRAL"
  | "SATISFIED"
  | "FRUSTRATED"
  | "UPSET"
  | "DISTRESSED";

export type EmotionIntensity = "LOW" | "MEDIUM" | "HIGH";

export type NoiseSeverity = "NONE" | "LOW" | "MEDIUM" | "HIGH";

export type NoiseType =
  | "NONE"
  | "OFFICE_CHATTER"
  | "TV"
  | "TRAFFIC"
  | "MUSIC"
  | "WIND"
  | "STATIC"
  | "KEYBOARD"
  | "MECHANICAL"
  | "OTHER";

export type AudioQuality =
  | "CLEAR"
  | "SLIGHTLY_IMPAIRED"
  | "SEVERELY_IMPAIRED";

export type HealthState = "healthy" | "unhealthy" | "degraded";

// ---------- Upload ----------

export interface RejectedFile {
  filename: string;
  reason: string;
}

export interface UploadResultData {
  batch_id: string;
  job_id: string;
  files_uploaded: number;
  files_rejected: number;
  rejected_files: RejectedFile[];
}

// ---------- Jobs ----------

export interface JobRead {
  id: string;
  batch_id: string;
  status: JobStatus;
  progress: number;
  retry_count: number;
  total_files: number;
  processed_files: number;
  failed_files: number;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface JobProgressData {
  job_id: string;
  status: JobStatus;
  total_files: number;
  processed_files: number;
  failed_files: number;
  progress_percentage: number;
  elapsed_time_ms: number | null;
  retry_count: number;
  error_message: string | null;
}

export interface JobListData {
  items: JobRead[];
  count: number;
}

export interface StartJobData {
  job: JobRead;
  queued: boolean;
}

export interface JobActionData {
  job: JobRead;
  detail: Record<string, unknown>;
}

// ---------- Audio ----------

export interface AudioAssetRead {
  id: string;
  batch_id: string;
  filename: string;
  format: string;
  extension: string;
  mime_type: string;
  size_bytes: number;
  duration: number | null;
  sample_rate: number | null;
  channels: number | null;
  storage_key: string;
  normalized_storage_key: string | null;
  processing_status: AudioStatus;
  is_preprocessed: boolean;
  preprocessed_at: string | null;
  analysis_completed: boolean;
  analysis_storage_key: string | null;
  analysis_version: string | null;
  analysis_completed_at: string | null;
  technical_completed_at: string | null;
  acoustic_completed_at: string | null;
  speech_completed_at: string | null;
  timing_json: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface AudioMetadataRead {
  audio_id: string;
  metadata: Record<string, unknown>;
  is_preprocessed: boolean;
}

export interface AudioDownloadData {
  audio_id: string;
  url: string;
  storage_key: string;
  content_variant: string;
  expires_in: number;
}

export interface AudioAnalysisRead {
  audio_id: string;
  analysis_completed: boolean;
  analysis_version: string | null;
  analysis_storage_key: string | null;
  analysis: Record<string, unknown>;
}

export interface AudioTechnicalRead {
  audio_id: string;
  audio_quality: AudioQuality | string;
  speaker_overlap_present: boolean;
  long_silence_present: boolean;
  technical_version: string | null;
  technical_completed: boolean;
}

export interface AudioAcousticRead {
  audio_id: string;
  background_noise_present: boolean;
  background_noise_type: NoiseType | string;
  background_noise_severity: NoiseSeverity | string;
  acoustic_version: string | null;
  acoustic_completed: boolean;
}

export interface AudioSpeechRead {
  audio_id: string;
  emotional_tone: EmotionTone | string;
  emotional_intensity: EmotionIntensity | string;
  speech_version: string | null;
  speech_completed: boolean;
}

export interface TimeSegment {
  start: number;
  end: number;
}

export interface AudioSegmentsRead {
  audio_id: string;
  speech_segments: TimeSegment[];
  silence_segments: TimeSegment[];
  speech_duration: number;
  speech_ratio: number;
  largest_silence: number;
  speech_start: number | null;
  speech_end: number | null;
}

// ---------- Prediction ----------

export interface AssessmentPrediction {
  emotional_tone: EmotionTone;
  emotional_intensity: EmotionIntensity;
  background_noise_present: boolean;
  background_noise_type: NoiseType;
  background_noise_severity: NoiseSeverity;
  audio_quality: AudioQuality;
  speaker_overlap_present: boolean;
  long_silence_present: boolean;
  confidence: number;
}

export interface PredictionRead {
  audio_id: string;
  prediction_version: string | null;
  prediction: AssessmentPrediction;
}

export interface PredictionListRead {
  count: number;
  predictions: PredictionRead[];
}

// ---------- Evaluation / Batches ----------

export interface BatchRunRead {
  batch_id: string;
  job_id: string;
  status: string;
  queued: boolean;
  already_running: boolean;
}

export interface BatchDeleteRead {
  batch_id: string;
  job_cancelled: boolean;
  deleted_objects: number;
}

export interface BatchStatusRead {
  batch_id: string;
  job_id: string | null;
  status: string;
  progress: number;
  total_files: number;
  processed_files: number;
  failed_files: number;
  started_at: string | null;
  completed_at: string | null;
  estimated_remaining_seconds: number | null;
}

export interface BatchMetricsRead {
  batch_id: string;
  total_audio: number;
  successful_predictions: number;
  failed_predictions: number;
  success_rate: number;
  average_processing_time_ms: number | null;
  min_processing_time_ms: number | null;
  max_processing_time_ms: number | null;
  average_confidence: number | null;
  batch_duration_ms: number | null;
  computed_at: string;
}

export interface BatchExportItem {
  name: string;
  storage_key: string;
  url: string;
  expires_in: number;
}

export interface BatchExportsRead {
  batch_id: string;
  exports: BatchExportItem[];
}

export interface BatchExportResultRow {
  filename: string;
  result: AssessmentPrediction;
}

export interface BatchExportJsonRead {
  batch_id: string;
  count: number;
  results: BatchExportResultRow[];
}

// ---------- System ----------

export interface SystemMetricsRead {
  database: boolean;
  redis: boolean;
  r2: boolean;
  celery: boolean;
  model_loaded: boolean;
  worker_count: number;
  system_version: string;
  checked_at: string;
}

export interface WorkerRead {
  worker_id: string;
  status: string;
  last_heartbeat: string | null;
  stale: boolean;
}

export interface WorkersRead {
  worker_count: number;
  stale_count: number;
  workers: WorkerRead[];
}

export interface BenchmarkRead {
  batch_id: string;
  total_files: number;
  successful_files: number;
  failed_files: number;
  average_latency_ms: number | null;
  p50_latency_ms: number | null;
  p95_latency_ms: number | null;
  p99_latency_ms: number | null;
  batch_duration_ms: number | null;
  throughput_files_per_minute: number | null;
  average_confidence: number | null;
  failure_rate: number;
}

// ---------- Health ----------

export interface HealthData {
  status: HealthState;
  service: string;
  version: string;
  environment: string;
}

export interface ComponentHealth {
  status: HealthState;
  component: string;
  details: Record<string, unknown>;
}

export interface ReadinessData {
  status: HealthState;
  service: string;
  system_version: string;
  model_loaded: boolean;
  worker_count: number;
  components: Record<string, ComponentHealth>;
}

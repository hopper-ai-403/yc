export const PIPELINE_STAGES = [
  "upload",
  "preprocessing",
  "analysis",
  "technical",
  "acoustic",
  "speech",
  "prediction",
] as const;

export type PipelineStage = (typeof PIPELINE_STAGES)[number];

export function stageDurationMs(
  timing: Record<string, unknown> | null | undefined,
  stage: PipelineStage,
): number | null {
  const value = timing?.[`${stage}_duration_ms`];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function totalDurationMs(
  timing: Record<string, unknown> | null | undefined,
): number | null {
  const value = timing?.total_pipeline_duration_ms;
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

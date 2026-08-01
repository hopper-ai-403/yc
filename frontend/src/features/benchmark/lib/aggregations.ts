import {
  PIPELINE_STAGES,
  stageDurationMs,
  totalDurationMs,
  type PipelineStage,
} from "@/features/audio/lib/timing";
import type { AssessmentPrediction, BatchExportResultRow } from "@/types/domain";

export { PIPELINE_STAGES, type PipelineStage };

export interface StageStats {
  stage: PipelineStage | "total";
  label: string;
  average: number;
  min: number;
  max: number;
  percentOfTotal: number;
}

const STAGE_LABELS: Record<PipelineStage | "total", string> = {
  upload: "Upload",
  preprocessing: "Preprocessing",
  analysis: "Analysis",
  technical: "Technical",
  acoustic: "Acoustic",
  speech: "Speech",
  prediction: "Prediction",
  total: "Total",
};

export function aggregateStageStats(
  timings: Record<string, unknown>[],
): StageStats[] {
  if (timings.length === 0) return [];

  const totals = timings
    .map((timing) => totalDurationMs(timing))
    .filter((value): value is number => value !== null && value > 0);
  const avgTotal =
    totals.length > 0 ? totals.reduce((a, b) => a + b, 0) / totals.length : 0;

  const stages: StageStats[] = PIPELINE_STAGES.map((stage) => {
    const values = timings
      .map((timing) => stageDurationMs(timing, stage))
      .filter((value): value is number => value !== null && value >= 0);
    if (values.length === 0) {
      return {
        stage,
        label: STAGE_LABELS[stage],
        average: 0,
        min: 0,
        max: 0,
        percentOfTotal: 0,
      };
    }
    const average = values.reduce((a, b) => a + b, 0) / values.length;
    return {
      stage,
      label: STAGE_LABELS[stage],
      average,
      min: Math.min(...values),
      max: Math.max(...values),
      percentOfTotal: avgTotal > 0 ? (average / avgTotal) * 100 : 0,
    };
  });

  if (avgTotal > 0) {
    stages.push({
      stage: "total",
      label: STAGE_LABELS.total,
      average: avgTotal,
      min: Math.min(...totals),
      max: Math.max(...totals),
      percentOfTotal: 100,
    });
  }

  return stages;
}

/** Stacked-bar row: one segment per stage (excludes total). */
export function stackedLatencyRow(stats: StageStats[]): Record<string, number | string> {
  const row: Record<string, number | string> = { name: "Average latency" };
  for (const stage of stats) {
    if (stage.stage === "total") continue;
    row[stage.label] = Math.round(stage.average * 100) / 100;
  }
  return row;
}

export function confidenceBuckets(
  results: BatchExportResultRow[],
  bucketCount = 10,
): Array<{ bucket: string; count: number; mid: number }> {
  const buckets = Array.from({ length: bucketCount }, (_, index) => ({
    bucket: `${(index / bucketCount).toFixed(1)}–${((index + 1) / bucketCount).toFixed(1)}`,
    count: 0,
    mid: (index + 0.5) / bucketCount,
  }));
  for (const row of results) {
    const confidence = row.result.confidence;
    if (!Number.isFinite(confidence)) continue;
    const clamped = Math.min(0.999, Math.max(0, confidence));
    const index = Math.floor(clamped * bucketCount);
    buckets[index].count += 1;
  }
  return buckets;
}

export function median(values: number[]): number | null {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0
    ? (sorted[mid - 1] + sorted[mid]) / 2
    : sorted[mid];
}

export type DistributionField = keyof Pick<
  AssessmentPrediction,
  | "emotional_tone"
  | "background_noise_type"
  | "background_noise_severity"
  | "audio_quality"
>;

export function distribution(
  results: BatchExportResultRow[],
  field: DistributionField,
): Array<{ name: string; value: number }> {
  const counts = new Map<string, number>();
  for (const row of results) {
    const key = String(row.result[field]);
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return [...counts.entries()]
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value);
}

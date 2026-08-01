"use client";

import { useMemo } from "react";
import { useQueries, useQuery } from "@tanstack/react-query";

import { createQueryKeys } from "@/features/shared/query-keys";
import { QUERY_STALE_TIME_MS } from "@/lib/constants";
import { getBatchExportJson, getBatchMetrics, listJobs } from "@/services/batch";
import { getBatchBenchmark } from "@/services/benchmark";
import { getAudioAsset } from "@/services/audio";
import { getBatchPredictions } from "@/services/prediction";
import { getSystemMetrics } from "@/services/system";
import type {
  AssessmentPrediction,
  BatchExportJsonRead,
  BatchMetricsRead,
  BenchmarkRead,
  JobRead,
  PredictionListRead,
} from "@/types/domain";

export const benchmarkKeys = createQueryKeys("benchmark");

export function useCompletedJobs(limit = 50) {
  return useQuery({
    queryKey: benchmarkKeys.list({ status: "COMPLETED", limit }),
    queryFn: () => listJobs({ status: "COMPLETED", limit }),
    staleTime: QUERY_STALE_TIME_MS,
  });
}

export function useBatchBenchmark(batchId: string | null) {
  return useQuery({
    queryKey: benchmarkKeys.detail(batchId ?? "none"),
    queryFn: () => getBatchBenchmark(batchId!),
    enabled: Boolean(batchId),
    staleTime: 60_000,
    retry: false,
  });
}

export function useBatchExportResults(batchId: string | null) {
  return useQuery({
    queryKey: [...benchmarkKeys.detail(batchId ?? "none"), "export"] as const,
    queryFn: () => getBatchExportJson(batchId!),
    enabled: Boolean(batchId),
    staleTime: 60_000,
    retry: false,
  });
}

export function useBatchPredictionsList(batchId: string | null) {
  return useQuery({
    queryKey: [...benchmarkKeys.detail(batchId ?? "none"), "predictions"] as const,
    queryFn: () => getBatchPredictions(batchId!),
    enabled: Boolean(batchId),
    staleTime: 60_000,
    retry: false,
  });
}

export function useBatchMetrics(batchId: string | null) {
  return useQuery({
    queryKey: [...benchmarkKeys.detail(batchId ?? "none"), "metrics"] as const,
    queryFn: () => getBatchMetrics(batchId!),
    enabled: Boolean(batchId),
    staleTime: 60_000,
    retry: false,
  });
}

export function useWorkersCount() {
  return useQuery({
    queryKey: [...benchmarkKeys.all, "workers"] as const,
    queryFn: getSystemMetrics,
    staleTime: QUERY_STALE_TIME_MS,
  });
}

/**
 * Sample timing_json from audio assets referenced by batch predictions.
 * Bounded to avoid N+1 fan-out on large batches.
 */
export function useStageTimingSample(
  predictions: PredictionListRead | undefined,
  sampleSize = 20,
) {
  const audioIds = useMemo(() => {
    const ids = predictions?.predictions.map((p) => p.audio_id) ?? [];
    return ids.slice(0, sampleSize);
  }, [predictions]);

  const queries = useQueries({
    queries: audioIds.map((audioId) => ({
      queryKey: [...benchmarkKeys.all, "timing", audioId] as const,
      queryFn: () => getAudioAsset(audioId),
      staleTime: Infinity,
      retry: false,
    })),
  });

  return useMemo(() => {
    const timings = queries
      .map((query) => query.data?.timing_json ?? null)
      .filter((value): value is Record<string, unknown> => value !== null);
    return {
      timings,
      isLoading: queries.some((query) => query.isLoading),
      sampleSize: audioIds.length,
    };
  }, [queries, audioIds.length]);
}

/** Benchmarks for a table of completed jobs (capped). */
export function useBenchmarksForJobs(jobs: JobRead[], limit = 8) {
  const selected = useMemo(() => jobs.slice(0, limit), [jobs, limit]);
  const queries = useQueries({
    queries: selected.map((job) => ({
      queryKey: benchmarkKeys.detail(job.batch_id),
      queryFn: () => getBatchBenchmark(job.batch_id),
      staleTime: 5 * 60_000,
      retry: false,
    })),
  });

  return useMemo(() => {
    const rows: Array<{
      job: JobRead;
      benchmark: BenchmarkRead | null;
      metrics: null;
    }> = selected.map((job, index) => ({
      job,
      benchmark: queries[index]?.data ?? null,
      metrics: null,
    }));
    return {
      rows,
      byBatchId: new Map(
        queries
          .map((query, index) => [selected[index]?.batch_id, query.data] as const)
          .filter((entry): entry is [string, BenchmarkRead] =>
            Boolean(entry[0] && entry[1]),
          ),
      ),
      isLoading: queries.some((query) => query.isLoading),
    };
  }, [queries, selected]);
}

export function useMetricsForJobs(jobs: JobRead[], limit = 8) {
  const selected = useMemo(() => jobs.slice(0, limit), [jobs, limit]);
  const queries = useQueries({
    queries: selected.map((job) => ({
      queryKey: [...benchmarkKeys.detail(job.batch_id), "metrics"] as const,
      queryFn: () => getBatchMetrics(job.batch_id),
      staleTime: 5 * 60_000,
      retry: false,
    })),
  });

  return useMemo(() => {
    const byBatchId = new Map<string, BatchMetricsRead>();
    queries.forEach((query, index) => {
      const batchId = selected[index]?.batch_id;
      if (batchId && query.data) byBatchId.set(batchId, query.data);
    });
    return { byBatchId, isLoading: queries.some((query) => query.isLoading) };
  }, [queries, selected]);
}

export type { AssessmentPrediction, BatchExportJsonRead, BenchmarkRead };

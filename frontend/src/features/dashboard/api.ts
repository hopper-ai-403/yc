"use client";

import { useMemo } from "react";
import { useQueries, useQuery } from "@tanstack/react-query";

import { createQueryKeys } from "@/features/shared/query-keys";
import {
  QUERY_STALE_TIME_MS,
  SYSTEM_METRICS_REFETCH_MS,
} from "@/lib/constants";
import { getBatchMetrics, listJobs } from "@/services/batch";
import { getHealth, getSystemMetrics } from "@/services/system";
import type {
  BatchMetricsRead,
  JobListData,
  JobRead,
  JobStatus,
} from "@/types/domain";

export const jobsKeys = createQueryKeys("jobs");
export const metricsKeys = createQueryKeys("batch-metrics");
export const systemKeys = createQueryKeys("system");

/** Cap on per-batch metrics fetches to avoid N+1 fan-out on large lists. */
export const MAX_METRICS_LOOKUPS = 10;

export function useJobsList(params?: {
  status?: JobStatus;
  limit?: number;
  offset?: number;
}) {
  return useQuery<JobListData>({
    queryKey: jobsKeys.list(params),
    queryFn: () => listJobs(params),
    staleTime: QUERY_STALE_TIME_MS,
    refetchInterval: (query) => {
      const data = query.state.data;
      const active = data?.items.some(
        (job) => job.status === "RUNNING" || job.status === "QUEUED",
      );
      return active ? 4_000 : false;
    },
  });
}

export function useSystemMetrics() {
  return useQuery({
    queryKey: systemKeys.list({ resource: "metrics" }),
    queryFn: getSystemMetrics,
    staleTime: QUERY_STALE_TIME_MS,
    refetchInterval: SYSTEM_METRICS_REFETCH_MS,
  });
}

export function useBackendHealth() {
  return useQuery({
    queryKey: systemKeys.list({ resource: "health" }),
    queryFn: getHealth,
    staleTime: QUERY_STALE_TIME_MS,
    refetchInterval: SYSTEM_METRICS_REFETCH_MS,
    retry: 1,
  });
}

/**
 * Fetch metrics for a bounded set of completed jobs.
 * Metrics only exist for completed batches; lookups are skipped otherwise.
 */
export function useBatchMetricsForJobs(jobs: JobRead[]) {
  const completed = useMemo(
    () =>
      jobs
        .filter((job) => job.status === "COMPLETED")
        .slice(0, MAX_METRICS_LOOKUPS),
    [jobs],
  );
  const queries = useQueries({
    queries: completed.map((job) => ({
      queryKey: metricsKeys.detail(job.batch_id),
      queryFn: () => getBatchMetrics(job.batch_id),
      staleTime: 5 * 60_000,
      retry: false,
    })),
  });

  return useMemo(() => {
    const byBatchId = new Map<string, BatchMetricsRead>();
    queries.forEach((query, index) => {
      const batchId = completed[index]?.batch_id;
      if (batchId && query.data) {
        byBatchId.set(batchId, query.data);
      }
    });
    return {
      byBatchId,
      isLoading: queries.some((query) => query.isLoading),
    };
  }, [queries, completed]);
}

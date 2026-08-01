"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";

import { EmptyState, EmptyStateAction, ErrorState, QuickActions } from "@/components/common";
import { PageContainer, PageHeader } from "@/components/layout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { SectionSkeleton } from "@/features/audio/components/section";
import {
  useBatchBenchmark,
  useBatchExportResults,
  useBatchPredictionsList,
  useBenchmarksForJobs,
  useCompletedJobs,
  useMetricsForJobs,
  useStageTimingSample,
  useWorkersCount,
} from "@/features/benchmark/api";
import { BatchPerformanceTable } from "@/features/benchmark/components/batch-performance-table";
import { BatchSelector } from "@/features/benchmark/components/batch-selector";
import { BenchmarkMetrics } from "@/features/benchmark/components/benchmark-metrics";
import {
  aggregateStageStats,
  confidenceBuckets,
  distribution,
  median,
} from "@/features/benchmark/lib/aggregations";
import {
  formatConfidence,
  formatDurationMs,
  formatPercent,
} from "@/lib/format";
import { ROUTES } from "@/lib/constants";
import { RefreshCw, Upload } from "lucide-react";

const LatencyStackedChart = dynamic(
  () =>
    import("@/features/benchmark/components/charts").then(
      (mod) => mod.LatencyStackedChart,
    ),
  { ssr: false, loading: () => <SectionSkeleton rows={3} /> },
);
const ConfidenceHistogram = dynamic(
  () =>
    import("@/features/benchmark/components/charts").then(
      (mod) => mod.ConfidenceHistogram,
    ),
  { ssr: false, loading: () => <SectionSkeleton rows={4} /> },
);
const DistributionBarChart = dynamic(
  () =>
    import("@/features/benchmark/components/charts").then(
      (mod) => mod.DistributionBarChart,
    ),
  { ssr: false, loading: () => <SectionSkeleton rows={4} /> },
);
const DistributionPieChart = dynamic(
  () =>
    import("@/features/benchmark/components/charts").then(
      (mod) => mod.DistributionPieChart,
    ),
  { ssr: false, loading: () => <SectionSkeleton rows={4} /> },
);

export function BenchmarkDashboard() {
  const searchParams = useSearchParams();
  const jobsQuery = useCompletedJobs();
  const jobs = useMemo(() => jobsQuery.data?.items ?? [], [jobsQuery.data]);
  const [batchId, setBatchId] = useState<string | null>(null);

  useEffect(() => {
    const fromQuery = searchParams.get("batch");
    if (fromQuery) {
      setBatchId(fromQuery);
      return;
    }
    if (!batchId && jobs[0]) setBatchId(jobs[0].batch_id);
  }, [searchParams, jobs, batchId]);

  const benchmarkQuery = useBatchBenchmark(batchId);
  const exportQuery = useBatchExportResults(batchId);
  const predictionsQuery = useBatchPredictionsList(batchId);
  const workersQuery = useWorkersCount();
  const timingSample = useStageTimingSample(predictionsQuery.data);
  const tableBenchmarks = useBenchmarksForJobs(jobs);
  const tableMetrics = useMetricsForJobs(jobs);

  const stageStats = useMemo(
    () => aggregateStageStats(timingSample.timings),
    [timingSample.timings],
  );

  const results = useMemo(
    () => exportQuery.data?.results ?? [],
    [exportQuery.data],
  );
  const confidences = useMemo(
    () => results.map((row) => row.result.confidence).filter(Number.isFinite),
    [results],
  );
  const buckets = useMemo(() => confidenceBuckets(results), [results]);
  const emotionDist = useMemo(
    () => distribution(results, "emotional_tone"),
    [results],
  );
  const noiseTypeDist = useMemo(
    () => distribution(results, "background_noise_type"),
    [results],
  );
  const noiseSeverityDist = useMemo(
    () => distribution(results, "background_noise_severity"),
    [results],
  );
  const qualityDist = useMemo(
    () => distribution(results, "audio_quality"),
    [results],
  );

  const loadingTop =
    jobsQuery.isLoading || (Boolean(batchId) && benchmarkQuery.isLoading);

  return (
    <PageContainer className="max-w-7xl">
      <PageHeader
        title="Benchmark Dashboard"
        description="Latency percentiles, throughput, confidence, and prediction distributions for completed evaluation batches."
        actions={
          <QuickActions
            actions={[
              {
                id: "refresh",
                label: "Refresh",
                icon: RefreshCw,
                shortcut: "R",
                disabled: jobsQuery.isFetching || benchmarkQuery.isFetching,
                onClick: () => {
                  void jobsQuery.refetch();
                  void benchmarkQuery.refetch();
                  void exportQuery.refetch();
                },
              },
              {
                id: "upload",
                label: "Upload",
                icon: Upload,
                href: ROUTES.upload,
                variant: "default",
                shortcut: "U",
              },
            ]}
          />
        }
      />

      <div className="space-y-2">
        <p className="text-xs font-medium text-muted-foreground">Batch</p>
        <BatchSelector
          jobs={jobs}
          value={batchId}
          onChange={setBatchId}
          loading={jobsQuery.isLoading}
        />
      </div>

      {jobsQuery.isError ? (
        <ErrorState
          error={jobsQuery.error}
          title="Failed to load completed batches"
          onRetry={() => void jobsQuery.refetch()}
        />
      ) : jobs.length === 0 && !jobsQuery.isLoading ? (
        <EmptyState
          title="No completed batches"
          description="Upload audio and finish a batch to generate benchmark reports."
          action={<EmptyStateAction label="Upload audio" href={ROUTES.upload} />}
          secondaryAction={
            <EmptyStateAction label="View batches" href={ROUTES.batches} />
          }
          hint="Press G anytime to return here"
        />
      ) : (
        <>
          {benchmarkQuery.isError ? (
            <ErrorState
              error={benchmarkQuery.error}
              title="Failed to load benchmark"
              onRetry={() => void benchmarkQuery.refetch()}
            />
          ) : (
            <BenchmarkMetrics
              benchmark={benchmarkQuery.data ?? null}
              workerCount={workersQuery.data?.worker_count ?? null}
              loading={loadingTop}
            />
          )}

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Latency by Stage</CardTitle>
                <p className="text-xs text-muted-foreground">
                  Stacked average durations from{" "}
                  {timingSample.sampleSize || "—"} sampled files
                </p>
              </CardHeader>
              <CardContent>
                {timingSample.isLoading ? (
                  <SectionSkeleton rows={3} />
                ) : (
                  <LatencyStackedChart stats={stageStats} />
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Pipeline Breakdown</CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                {timingSample.isLoading ? (
                  <div className="space-y-2 p-4">
                    {Array.from({ length: 5 }, (_, index) => (
                      <Skeleton key={index} className="h-8 w-full" />
                    ))}
                  </div>
                ) : stageStats.length === 0 ? (
                  <p className="p-6 text-center text-xs text-muted-foreground">
                    Timing metadata not yet available for this batch.
                  </p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-border text-left text-xs text-muted-foreground">
                          <th className="px-4 py-2.5 font-medium">Stage</th>
                          <th className="px-4 py-2.5 font-medium">Average</th>
                          <th className="px-4 py-2.5 font-medium">Min</th>
                          <th className="px-4 py-2.5 font-medium">Max</th>
                          <th className="px-4 py-2.5 font-medium">% of total</th>
                        </tr>
                      </thead>
                      <tbody>
                        {stageStats.map((stage) => (
                          <tr
                            key={stage.stage}
                            className="border-b border-border/60 last:border-0"
                          >
                            <td className="px-4 py-2.5 text-xs font-medium">
                              {stage.label}
                            </td>
                            <td className="px-4 py-2.5 font-mono text-xs tabular-nums">
                              {formatDurationMs(stage.average)}
                            </td>
                            <td className="px-4 py-2.5 font-mono text-xs tabular-nums text-muted-foreground">
                              {formatDurationMs(stage.min)}
                            </td>
                            <td className="px-4 py-2.5 font-mono text-xs tabular-nums text-muted-foreground">
                              {formatDurationMs(stage.max)}
                            </td>
                            <td className="px-4 py-2.5 font-mono text-xs tabular-nums">
                              {formatPercent(stage.percentOfTotal / 100)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Confidence Distribution</CardTitle>
                <p className="text-xs text-muted-foreground">
                  Avg {formatConfidence(
                    confidences.length
                      ? confidences.reduce((a, b) => a + b, 0) / confidences.length
                      : null,
                  )}{" "}
                  · Median {formatConfidence(median(confidences))}
                </p>
              </CardHeader>
              <CardContent>
                {exportQuery.isLoading ? (
                  <SectionSkeleton rows={4} />
                ) : exportQuery.isError ? (
                  <ErrorState
                    error={exportQuery.error}
                    title="Failed to load predictions"
                    onRetry={() => void exportQuery.refetch()}
                  />
                ) : (
                  <ConfidenceHistogram data={buckets} />
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Emotion Distribution</CardTitle>
              </CardHeader>
              <CardContent>
                {exportQuery.isLoading ? (
                  <SectionSkeleton rows={4} />
                ) : (
                  <DistributionPieChart
                    data={emotionDist}
                    label="Emotion distribution"
                  />
                )}
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            <Card>
              <CardHeader>
                <CardTitle>Noise Type</CardTitle>
              </CardHeader>
              <CardContent>
                {exportQuery.isLoading ? (
                  <SectionSkeleton rows={4} />
                ) : (
                  <DistributionBarChart
                    data={noiseTypeDist}
                    label="Noise type distribution"
                  />
                )}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Noise Severity</CardTitle>
              </CardHeader>
              <CardContent>
                {exportQuery.isLoading ? (
                  <SectionSkeleton rows={4} />
                ) : (
                  <DistributionBarChart
                    data={noiseSeverityDist}
                    label="Noise severity distribution"
                  />
                )}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Audio Quality</CardTitle>
              </CardHeader>
              <CardContent>
                {exportQuery.isLoading ? (
                  <SectionSkeleton rows={4} />
                ) : (
                  <DistributionBarChart
                    data={qualityDist}
                    label="Audio quality distribution"
                  />
                )}
              </CardContent>
            </Card>
          </div>

          <BatchPerformanceTable
            jobs={jobs.slice(0, 8)}
            benchmarks={tableBenchmarks.byBatchId}
            metrics={tableMetrics.byBatchId}
            loading={tableBenchmarks.isLoading || tableMetrics.isLoading}
          />
        </>
      )}
    </PageContainer>
  );
}

"use client";

import {
  ArrowLeft,
  Copy,
  Eye,
  Gauge,
  RefreshCw,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import {
  EmptyState,
  ErrorState,
  MetricCard,
  ProgressBar,
  QuickActions,
  StatusBadge,
} from "@/components/common";
import { PageContainer, PageHeader } from "@/components/layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { jobsKeys, metricsKeys } from "@/features/dashboard/api";
import { ExportButtons, useExportActions } from "@/features/shared/export-actions";
import { useCopyToClipboard } from "@/hooks/use-copy-to-clipboard";
import { JOB_PROGRESS_REFETCH_MS, ROUTES } from "@/lib/constants";
import {
  formatConfidence,
  formatDurationMs,
  formatPercent,
} from "@/lib/format";
import { notify } from "@/lib/notify";
import {
  getBatchExportJson,
  getBatchMetrics,
  getBatchStatus,
} from "@/services/batch";
import { getBatchPredictions } from "@/services/prediction";
import { useUiStore } from "@/stores/ui-store";
import type {
  AssessmentPrediction,
  BatchExportJsonRead,
  PredictionRead,
} from "@/types/domain";

type ResultRow = {
  key: string;
  audioId: string | null;
  filename: string;
  result: AssessmentPrediction;
};

function rowsFromPredictions(predictions: PredictionRead[]): ResultRow[] {
  return predictions.map((item) => ({
    key: item.audio_id,
    audioId: item.audio_id,
    filename: item.filename?.trim() || item.audio_id,
    result: item.prediction,
  }));
}

function rowsFromExport(exportData: BatchExportJsonRead): ResultRow[] {
  return exportData.results.map((row, index) => ({
    key: `${row.filename}-${index}`,
    audioId: null,
    filename: row.filename,
    result: row.result,
  }));
}

export function BatchDetailView({ batchId }: { batchId: string }) {
  const openDrawer = useUiStore((s) => s.openDrawer);
  const { copy } = useCopyToClipboard();

  const statusQuery = useQuery({
    queryKey: jobsKeys.list({ resource: "batch-status", batchId }),
    queryFn: () => getBatchStatus(batchId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "RUNNING" || status === "QUEUED"
        ? JOB_PROGRESS_REFETCH_MS
        : false;
    },
  });

  const status = statusQuery.data;
  const isActive =
    status?.status === "RUNNING" || status?.status === "QUEUED";
  const isCompleted = status?.status === "COMPLETED";

  const metricsQuery = useQuery({
    queryKey: metricsKeys.detail(batchId),
    queryFn: () => getBatchMetrics(batchId),
    retry: false,
    enabled: isCompleted,
  });

  const predictionsQuery = useQuery({
    queryKey: ["predictions", "batch", batchId],
    queryFn: () => getBatchPredictions(batchId),
    retry: false,
    enabled: Boolean(status),
    refetchInterval: isActive ? JOB_PROGRESS_REFETCH_MS : false,
  });

  const resultsQuery = useQuery<BatchExportJsonRead>({
    queryKey: metricsKeys.list({ resource: "results", batchId }),
    queryFn: () => getBatchExportJson(batchId),
    retry: false,
    enabled: isCompleted,
  });

  const exports = useExportActions();
  const metrics = metricsQuery.data;

  const resultRows = useMemo(() => {
    const live = predictionsQuery.data?.predictions ?? [];
    if (live.length > 0) return rowsFromPredictions(live);
    if (resultsQuery.data && resultsQuery.data.count > 0) {
      return rowsFromExport(resultsQuery.data);
    }
    return [];
  }, [predictionsQuery.data, resultsQuery.data]);

  useEffect(() => {
    function onRefresh() {
      void statusQuery.refetch();
      void metricsQuery.refetch();
      void resultsQuery.refetch();
      void predictionsQuery.refetch();
    }
    window.addEventListener("aip:refresh", onRefresh);
    return () => window.removeEventListener("aip:refresh", onRefresh);
  }, [statusQuery, metricsQuery, resultsQuery, predictionsQuery]);

  return (
    <PageContainer>
      <PageHeader
        title="Batch Detail"
        description={`Batch ${batchId}`}
        actions={
          <QuickActions
            actions={[
              {
                id: "copy",
                label: "Copy ID",
                icon: Copy,
                onClick: () => {
                  void copy(batchId).then((ok) => {
                    if (ok) notify.success("Batch ID copied");
                  });
                },
              },
              {
                id: "refresh",
                label: "Refresh",
                icon: RefreshCw,
                shortcut: "R",
                disabled: statusQuery.isFetching || predictionsQuery.isFetching,
                onClick: () => {
                  void statusQuery.refetch();
                  void predictionsQuery.refetch();
                },
              },
              {
                id: "benchmark",
                label: "Benchmark",
                icon: Gauge,
                href: `${ROUTES.benchmark}?batch=${batchId}`,
                shortcut: "G",
              },
            ]}
          />
        }
      />

      <div className="flex flex-wrap items-center justify-between gap-2">
        <Link
          href={ROUTES.batches}
          className="inline-flex items-center gap-1 text-xs text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="size-3" />
          All batches
          <kbd className="ml-1 rounded border border-border px-1 font-mono text-[10px]">
            B
          </kbd>
        </Link>
        <ExportButtons
          batchId={batchId}
          pending={exports.pending}
          onCsv={exports.exportCsv}
          onJson={exports.exportJson}
        />
      </div>

      {statusQuery.isError ? (
        <ErrorState
          error={statusQuery.error}
          title="Failed to load batch"
          onRetry={() => void statusQuery.refetch()}
        />
      ) : statusQuery.isLoading ? (
        <div className="grid gap-3 md:grid-cols-4" aria-busy="true">
          {Array.from({ length: 4 }, (_, index) => (
            <Skeleton key={index} className="h-24 w-full" />
          ))}
        </div>
      ) : status ? (
        <div className="space-y-6">
          <Card>
            <CardContent className="space-y-3 p-4">
              <div className="flex items-center justify-between gap-4">
                <StatusBadge status={status.status} />
                <span className="font-mono text-xs tabular-nums text-muted-foreground">
                  {status.processed_files}/{status.total_files} files
                  {status.failed_files > 0
                    ? ` · ${status.failed_files} failed`
                    : ""}
                </span>
              </div>
              <ProgressBar value={status.progress} failed={status.failed_files} />
              {status.estimated_remaining_seconds !== null ? (
                <p className="text-xs text-muted-foreground">
                  Estimated remaining:{" "}
                  {formatDurationMs(status.estimated_remaining_seconds * 1000)}
                </p>
              ) : null}
            </CardContent>
          </Card>

          {metricsQuery.isLoading ? (
            <div className="grid gap-3 md:grid-cols-4" aria-busy="true">
              {Array.from({ length: 4 }, (_, index) => (
                <Skeleton key={index} className="h-24 w-full" />
              ))}
            </div>
          ) : metrics ? (
            <div className="grid gap-3 md:grid-cols-4">
              <MetricCard
                label="Avg Confidence"
                value={formatConfidence(metrics.average_confidence)}
              />
              <MetricCard
                label="Success Rate"
                value={formatPercent(metrics.success_rate)}
                description={`${metrics.successful_predictions}/${metrics.total_audio} files`}
              />
              <MetricCard
                label="Avg Processing"
                value={formatDurationMs(metrics.average_processing_time_ms)}
                description="Per audio file"
              />
              <MetricCard
                label="Batch Duration"
                value={formatDurationMs(metrics.batch_duration_ms)}
              />
            </div>
          ) : null}

          <Card>
            <CardHeader className="flex-row items-center justify-between space-y-0">
              <CardTitle>Results</CardTitle>
              {resultRows.length > 0 ? (
                <span className="font-mono text-xs tabular-nums text-muted-foreground">
                  {resultRows.length}
                  {status.total_files > 0 ? ` / ${status.total_files}` : ""} ready
                </span>
              ) : null}
            </CardHeader>
            <CardContent className="p-0">
              {predictionsQuery.isLoading && resultRows.length === 0 ? (
                <div className="space-y-2 p-4" aria-busy="true">
                  {Array.from({ length: 3 }, (_, index) => (
                    <Skeleton key={index} className="h-8 w-full" />
                  ))}
                </div>
              ) : predictionsQuery.isError && resultRows.length === 0 ? (
                <div className="p-4">
                  <ErrorState
                    error={predictionsQuery.error}
                    title="Failed to load results"
                    onRetry={() => void predictionsQuery.refetch()}
                  />
                </div>
              ) : resultRows.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border text-left text-xs text-muted-foreground">
                        <th className="px-4 py-2.5 font-medium">Filename</th>
                        <th className="px-4 py-2.5 font-medium">Emotion</th>
                        <th className="px-4 py-2.5 font-medium">Intensity</th>
                        <th className="px-4 py-2.5 font-medium">Noise</th>
                        <th className="px-4 py-2.5 font-medium">Quality</th>
                        <th className="px-4 py-2.5 text-right font-medium">
                          Confidence
                        </th>
                        <th className="px-4 py-2.5 text-right font-medium">
                          Actions
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {resultRows.map((row) => (
                        <tr
                          key={row.key}
                          className="border-b border-border/60 last:border-0 hover:bg-accent/30"
                        >
                          <td className="max-w-56 truncate px-4 py-2.5 font-mono text-xs">
                            {row.filename}
                          </td>
                          <td className="px-4 py-2.5 text-xs">
                            {row.result.emotional_tone}
                          </td>
                          <td className="px-4 py-2.5 text-xs text-muted-foreground">
                            {row.result.emotional_intensity}
                          </td>
                          <td className="px-4 py-2.5 text-xs text-muted-foreground">
                            {row.result.background_noise_present
                              ? row.result.background_noise_type
                              : "NONE"}
                          </td>
                          <td className="px-4 py-2.5 text-xs text-muted-foreground">
                            {row.result.audio_quality}
                          </td>
                          <td className="px-4 py-2.5 text-right font-mono text-xs tabular-nums">
                            {formatConfidence(row.result.confidence)}
                          </td>
                          <td className="px-4 py-2.5">
                            <div className="flex items-center justify-end gap-1">
                              <Button
                                size="icon"
                                variant="ghost"
                                aria-label="Preview prediction"
                                onClick={() => {
                                  if (row.audioId) {
                                    openDrawer({
                                      kind: "prediction",
                                      id: row.audioId,
                                      title: row.filename,
                                    });
                                  } else {
                                    openDrawer({
                                      kind: "artifact",
                                      id: row.filename,
                                      title: row.filename,
                                      data: {
                                        ...row.result,
                                      } as unknown as Record<string, unknown>,
                                    });
                                  }
                                }}
                              >
                                <Eye />
                              </Button>
                              {row.audioId ? (
                                <Link href={ROUTES.audioDetail(row.audioId)}>
                                  <Button size="sm" variant="outline">
                                    Open
                                  </Button>
                                </Link>
                              ) : null}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="p-4">
                  <EmptyState
                    title="No results yet"
                    description={
                      isActive
                        ? "Waiting for the first file to finish. Completed predictions appear here automatically."
                        : "No predictions are available for this batch."
                    }
                    hint={
                      isActive
                        ? "Live results update as each audio completes"
                        : undefined
                    }
                  />
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      ) : null}
    </PageContainer>
  );
}

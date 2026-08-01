"use client";

import {
  ArrowLeft,
  Copy,
  Eye,
  Gauge,
  RefreshCw,
} from "lucide-react";
import Link from "next/link";
import { useEffect } from "react";
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
import type { BatchExportJsonRead } from "@/types/domain";

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

  const metricsQuery = useQuery({
    queryKey: metricsKeys.detail(batchId),
    queryFn: () => getBatchMetrics(batchId),
    retry: false,
    enabled: statusQuery.data?.status === "COMPLETED",
  });

  const resultsQuery = useQuery<BatchExportJsonRead>({
    queryKey: metricsKeys.list({ resource: "results", batchId }),
    queryFn: () => getBatchExportJson(batchId),
    retry: false,
    enabled: statusQuery.data?.status === "COMPLETED",
  });

  const predictionsQuery = useQuery({
    queryKey: ["predictions", "batch", batchId],
    queryFn: () => getBatchPredictions(batchId),
    retry: false,
    enabled: statusQuery.data?.status === "COMPLETED",
  });

  const exports = useExportActions();
  const status = statusQuery.data;
  const metrics = metricsQuery.data;

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
                disabled: statusQuery.isFetching,
                onClick: () => void statusQuery.refetch(),
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
            <CardHeader>
              <CardTitle>Results</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              {resultsQuery.isLoading || predictionsQuery.isLoading ? (
                <div className="space-y-2 p-4" aria-busy="true">
                  {Array.from({ length: 3 }, (_, index) => (
                    <Skeleton key={index} className="h-8 w-full" />
                  ))}
                </div>
              ) : resultsQuery.data && resultsQuery.data.count > 0 ? (
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
                      {resultsQuery.data.results.map((row, index) => {
                        const prediction =
                          predictionsQuery.data?.predictions[index];
                        const audioId = prediction?.audio_id;
                        return (
                          <tr
                            key={row.filename}
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
                                    if (audioId) {
                                      openDrawer({
                                        kind: "prediction",
                                        id: audioId,
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
                                {audioId ? (
                                  <Link href={ROUTES.audioDetail(audioId)}>
                                    <Button size="sm" variant="outline">
                                      Open
                                    </Button>
                                  </Link>
                                ) : null}
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="p-4">
                  <EmptyState
                    title="No results yet"
                    description={
                      status.status === "RUNNING" || status.status === "QUEUED"
                        ? "This batch is still processing. Results will appear automatically."
                        : "Results appear once the batch finishes processing."
                    }
                    hint="Polling stops when the job completes"
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

"use client";

import Link from "next/link";

import { ProgressBar, StatusBadge } from "@/components/common";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ExportButtons,
  useExportActions,
} from "@/features/shared/export-actions";
import { shortId } from "@/features/dashboard/components/recent-batches-table";
import { ROUTES } from "@/lib/constants";
import {
  formatConfidence,
  formatDurationMs,
  formatPercent,
} from "@/lib/format";
import type { BatchMetricsRead, BenchmarkRead, JobRead } from "@/types/domain";

interface BatchPerformanceTableProps {
  jobs: JobRead[];
  benchmarks: Map<string, BenchmarkRead>;
  metrics: Map<string, BatchMetricsRead>;
  loading: boolean;
}

export function BatchPerformanceTable({
  jobs,
  benchmarks,
  metrics,
  loading,
}: BatchPerformanceTableProps) {
  const exports = useExportActions();

  return (
    <Card>
      <CardHeader>
        <CardTitle>Batch Performance</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        {loading ? (
          <div className="space-y-2 p-4" aria-busy="true">
            {Array.from({ length: 5 }, (_, index) => (
              <Skeleton key={index} className="h-10 w-full" />
            ))}
          </div>
        ) : jobs.length === 0 ? (
          <p className="p-6 text-center text-xs text-muted-foreground">
            No completed batches to compare.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted-foreground">
                  <th className="px-4 py-2.5 font-medium">Batch</th>
                  <th className="px-4 py-2.5 font-medium">Files</th>
                  <th className="px-4 py-2.5 font-medium">Duration</th>
                  <th className="min-w-28 px-4 py-2.5 font-medium">Success</th>
                  <th className="px-4 py-2.5 font-medium">Avg Confidence</th>
                  <th className="px-4 py-2.5 font-medium">P95</th>
                  <th className="px-4 py-2.5 text-right font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => {
                  const benchmark = benchmarks.get(job.batch_id);
                  const metric = metrics.get(job.batch_id);
                  const successRate =
                    metric?.success_rate ??
                    (benchmark && benchmark.total_files > 0
                      ? benchmark.successful_files / benchmark.total_files
                      : null);
                  return (
                    <tr
                      key={job.id}
                      className="border-b border-border/60 last:border-0 hover:bg-accent/30"
                    >
                      <td className="px-4 py-3">
                        <Link
                          href={ROUTES.batchDetail(job.batch_id)}
                          className="font-mono text-xs underline-offset-4 hover:underline"
                        >
                          {shortId(job.batch_id)}
                        </Link>
                        <div className="mt-1">
                          <StatusBadge status={job.status} />
                        </div>
                      </td>
                      <td className="px-4 py-3 font-mono text-xs tabular-nums text-muted-foreground">
                        {job.total_files}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-xs text-muted-foreground">
                        {formatDurationMs(
                          benchmark?.batch_duration_ms ??
                            metric?.batch_duration_ms,
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <div className="space-y-1">
                          <ProgressBar
                            value={(successRate ?? 0) * 100}
                            showLabel
                          />
                          <span className="font-mono text-[10px] text-muted-foreground">
                            {formatPercent(successRate)}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-3 font-mono text-xs tabular-nums">
                        {formatConfidence(
                          benchmark?.average_confidence ??
                            metric?.average_confidence,
                        )}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-xs text-muted-foreground">
                        {formatDurationMs(benchmark?.p95_latency_ms)}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end gap-1">
                          <Link
                            href={`${ROUTES.benchmark}?batch=${job.batch_id}`}
                            className="inline-flex h-8 items-center rounded-md border border-border px-2.5 text-xs font-medium transition-colors hover:bg-accent"
                          >
                            Inspect
                          </Link>
                          <ExportButtons
                            batchId={job.batch_id}
                            pending={exports.pending}
                            onCsv={exports.exportCsv}
                            onJson={exports.exportJson}
                          />
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

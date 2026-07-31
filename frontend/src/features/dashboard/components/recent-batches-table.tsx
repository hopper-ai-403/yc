"use client";

import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { motion } from "framer-motion";

import {
  EmptyState,
  ProgressBar,
  StatusBadge,
} from "@/components/common";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ExportButtons } from "@/features/shared/export-actions";
import { ROUTES } from "@/lib/constants";
import {
  formatConfidence,
  formatDurationMs,
  formatRelativeTime,
} from "@/lib/format";
import type { BatchMetricsRead, JobRead } from "@/types/domain";

function jobDurationMs(job: JobRead): number | null {
  if (!job.started_at || !job.completed_at) return null;
  const start = new Date(job.started_at).getTime();
  const end = new Date(job.completed_at).getTime();
  if (Number.isNaN(start) || Number.isNaN(end) || end < start) return null;
  return end - start;
}

export function shortId(id: string): string {
  return id.split("-")[0] ?? id.slice(0, 8);
}

interface RecentBatchesTableProps {
  jobs: JobRead[];
  metricsByBatchId: Map<string, BatchMetricsRead>;
  loading: boolean;
  pending: string | null;
  onExportCsv: (batchId: string) => void;
  onExportJson: (batchId: string) => void;
}

export function RecentBatchesTable({
  jobs,
  metricsByBatchId,
  loading,
  pending,
  onExportCsv,
  onExportJson,
}: RecentBatchesTableProps) {
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle>Recent Batches</CardTitle>
        <Link
          href={ROUTES.batches}
          className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
        >
          View all
          <ArrowRight className="size-3" />
        </Link>
      </CardHeader>
      <CardContent className="p-0">
        {loading ? (
          <TableSkeleton rows={5} />
        ) : jobs.length === 0 ? (
          <div className="p-4">
            <EmptyState
              title="No batches yet"
              description="Upload a ZIP of call recordings to run your first analysis batch."
              action={
                <Link
                  href={ROUTES.upload}
                  className="inline-flex h-8 items-center justify-center gap-2 rounded-md bg-primary px-3 text-xs font-medium text-primary-foreground transition-colors hover:bg-primary/90"
                >
                  Upload audio
                </Link>
              }
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted-foreground">
                  <th className="px-4 py-2.5 font-medium">Batch</th>
                  <th className="px-4 py-2.5 font-medium">Uploaded</th>
                  <th className="px-4 py-2.5 font-medium">Files</th>
                  <th className="px-4 py-2.5 font-medium">Status</th>
                  <th className="min-w-32 px-4 py-2.5 font-medium">Progress</th>
                  <th className="px-4 py-2.5 font-medium">Confidence</th>
                  <th className="px-4 py-2.5 font-medium">Duration</th>
                  <th className="px-4 py-2.5 text-right font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job, index) => {
                  const metrics = metricsByBatchId.get(job.batch_id);
                  return (
                    <motion.tr
                      key={job.id}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ duration: 0.2, delay: index * 0.02 }}
                      className="border-b border-border/60 last:border-0 hover:bg-accent/30"
                    >
                      <td className="px-4 py-3">
                        <Link
                          href={ROUTES.batchDetail(job.batch_id)}
                          className="font-mono text-xs text-foreground underline-offset-4 hover:underline"
                        >
                          {shortId(job.batch_id)}
                        </Link>
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-xs text-muted-foreground">
                        {formatRelativeTime(job.created_at)}
                      </td>
                      <td className="px-4 py-3 font-mono text-xs tabular-nums text-muted-foreground">
                        {job.processed_files}/{job.total_files}
                        {job.failed_files > 0 ? (
                          <span className="text-destructive">
                            {" "}
                            (+{job.failed_files} failed)
                          </span>
                        ) : null}
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={job.status} />
                      </td>
                      <td className="px-4 py-3">
                        <ProgressBar
                          value={job.progress}
                          failed={job.failed_files}
                        />
                      </td>
                      <td className="px-4 py-3 font-mono text-xs tabular-nums">
                        {formatConfidence(metrics?.average_confidence)}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-xs text-muted-foreground">
                        {formatDurationMs(
                          metrics?.batch_duration_ms ?? jobDurationMs(job),
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end gap-1">
                          <Link
                            href={ROUTES.batchDetail(job.batch_id)}
                            aria-label="Open batch"
                            title="Open batch"
                            className="inline-flex size-9 items-center justify-center rounded-md transition-colors hover:bg-accent hover:text-accent-foreground [&_svg]:size-4"
                          >
                            <ArrowRight />
                          </Link>
                          <ExportButtons
                            batchId={job.batch_id}
                            pending={pending}
                            onCsv={onExportCsv}
                            onJson={onExportJson}
                          />
                        </div>
                      </td>
                    </motion.tr>
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

function TableSkeleton({ rows }: { rows: number }) {
  return (
    <div className="space-y-2 p-4" aria-busy="true" aria-label="Loading batches">
      {Array.from({ length: rows }, (_, index) => (
        <Skeleton key={index} className="h-10 w-full" />
      ))}
    </div>
  );
}

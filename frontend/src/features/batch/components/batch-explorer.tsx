"use client";

import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  Eye,
  FolderSearch,
  RefreshCw,
  Upload,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";

import {
  EmptyState,
  EmptyStateAction,
  ErrorState,
  FilterBar,
  Pagination,
  ProgressBar,
  QuickActions,
  SearchInput,
  StatusBadge,
} from "@/components/common";
import { PageContainer, PageHeader } from "@/components/layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useBatchMetricsForJobs,
  useJobsList,
} from "@/features/dashboard/api";
import {
  ExportButtons,
  useExportActions,
} from "@/features/shared/export-actions";
import { ROUTES } from "@/lib/constants";
import {
  formatConfidence,
  formatDateTime,
  formatDurationMs,
} from "@/lib/format";
import { useDebounce } from "@/hooks/use-debounce";
import { useUiStore } from "@/stores/ui-store";
import type { JobRead, JobStatus } from "@/types/domain";

import { shortId } from "@/features/dashboard/components/recent-batches-table";

const PAGE_SIZE = 10;

const STATUS_FILTERS: { value: JobStatus; label: string }[] = [
  { value: "RUNNING", label: "Running" },
  { value: "QUEUED", label: "Queued" },
  { value: "COMPLETED", label: "Completed" },
  { value: "FAILED", label: "Failed" },
];

const DATE_FILTERS = [
  { value: "24h", label: "Last 24h", ms: 24 * 3_600_000 },
  { value: "7d", label: "Last 7 days", ms: 7 * 86_400_000 },
  { value: "30d", label: "Last 30 days", ms: 30 * 86_400_000 },
] as const;

type SortKey = "created_at" | "progress" | "total_files";
type SortDirection = "asc" | "desc";

function jobDurationMs(job: JobRead): number | null {
  if (!job.started_at || !job.completed_at) return null;
  const start = new Date(job.started_at).getTime();
  const end = new Date(job.completed_at).getTime();
  if (Number.isNaN(start) || Number.isNaN(end) || end < start) return null;
  return end - start;
}

export function BatchExplorer() {
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [dateFilter, setDateFilter] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [sortKey, setSortKey] = useState<SortKey>("created_at");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");

  const debouncedSearch = useDebounce(search, 250);
  const exports = useExportActions();
  const openDrawer = useUiStore((s) => s.openDrawer);

  const jobsQuery = useJobsList({
    status: status ?? undefined,
    limit: PAGE_SIZE,
    offset: (page - 1) * PAGE_SIZE,
  });

  useEffect(() => {
    function onRefresh() {
      void jobsQuery.refetch();
    }
    window.addEventListener("aip:refresh", onRefresh);
    return () => window.removeEventListener("aip:refresh", onRefresh);
  }, [jobsQuery]);

  const items = useMemo(() => jobsQuery.data?.items ?? [], [jobsQuery.data]);
  const total = jobsQuery.data?.count ?? 0;

  const filtered = useMemo(() => {
    let rows = items;
    const needle = debouncedSearch.trim().toLowerCase();
    if (needle) {
      rows = rows.filter(
        (job) =>
          job.batch_id.toLowerCase().includes(needle) ||
          job.id.toLowerCase().includes(needle),
      );
    }
    const dateOption = DATE_FILTERS.find((option) => option.value === dateFilter);
    if (dateOption) {
      const cutoff = Date.now() - dateOption.ms;
      rows = rows.filter((job) => new Date(job.created_at).getTime() >= cutoff);
    }
    return rows;
  }, [items, debouncedSearch, dateFilter]);

  const sorted = useMemo(() => {
    const direction = sortDirection === "asc" ? 1 : -1;
    return [...filtered].sort((a, b) => {
      if (sortKey === "created_at") {
        return (
          (new Date(a.created_at).getTime() - new Date(b.created_at).getTime()) *
          direction
        );
      }
      return (a[sortKey] - b[sortKey]) * direction;
    });
  }, [filtered, sortKey, sortDirection]);

  const { byBatchId } = useBatchMetricsForJobs(sorted);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDirection((current) => (current === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDirection("desc");
    }
  };

  const sortIcon = (key: SortKey) => {
    if (sortKey !== key) return <ArrowUpDown className="size-3" />;
    return sortDirection === "asc" ? (
      <ArrowUp className="size-3" />
    ) : (
      <ArrowDown className="size-3" />
    );
  };

  return (
    <PageContainer>
      <PageHeader
        title="Batch Explorer"
        description="Search, filter, and inspect every processing batch."
        actions={
          <QuickActions
            actions={[
              {
                id: "refresh",
                label: "Refresh",
                icon: RefreshCw,
                shortcut: "R",
                disabled: jobsQuery.isFetching,
                onClick: () => void jobsQuery.refetch(),
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

      <div className="flex flex-wrap items-center gap-2">
        <SearchInput
          value={search}
          onChange={setSearch}
          placeholder="Search by batch or job ID…"
          className="w-full sm:w-72"
          aria-label="Search batches"
        />
        <FilterBar
          options={STATUS_FILTERS}
          value={status}
          onChange={(value) => {
            setStatus((value as JobStatus | null) ?? null);
            setPage(1);
          }}
          className="flex-1"
        />
        <FilterBar
          options={DATE_FILTERS.map((option) => ({
            value: option.value,
            label: option.label,
          }))}
          value={dateFilter}
          onChange={setDateFilter}
          allLabel="Any date"
        />
      </div>

      <Card>
        <CardContent className="p-0">
          {jobsQuery.isError ? (
            <div className="p-4">
              <ErrorState
                error={jobsQuery.error}
                title="Failed to load batches"
                onRetry={() => void jobsQuery.refetch()}
              />
            </div>
          ) : jobsQuery.isLoading ? (
            <div className="space-y-2 p-4" aria-busy="true" aria-label="Loading batches">
              {Array.from({ length: PAGE_SIZE }, (_, index) => (
                <Skeleton key={index} className="h-10 w-full" />
              ))}
            </div>
          ) : sorted.length === 0 ? (
            <div className="p-4">
              <EmptyState
                icon={FolderSearch}
                title={
                  debouncedSearch || status || dateFilter
                    ? "No batches match your filters"
                    : "No batches yet"
                }
                description={
                  debouncedSearch || status || dateFilter
                    ? "Try widening the date range or clearing the search."
                    : "Upload a ZIP of call recordings to create your first batch."
                }
                action={
                  debouncedSearch || status || dateFilter ? (
                    <EmptyStateAction
                      label="Clear filters"
                      onClick={() => {
                        setSearch("");
                        setStatus(null);
                        setDateFilter(null);
                      }}
                    />
                  ) : (
                    <EmptyStateAction label="Upload audio" href={ROUTES.upload} />
                  )
                }
                hint="Press U to open Upload Studio"
              />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs text-muted-foreground">
                    <th className="px-4 py-2.5 font-medium">Batch</th>
                    <th className="px-4 py-2.5 font-medium">
                      <button
                        type="button"
                        onClick={() => toggleSort("created_at")}
                        className="inline-flex items-center gap-1 font-medium hover:text-foreground"
                        aria-label="Sort by created date"
                      >
                        Created {sortIcon("created_at")}
                      </button>
                    </th>
                    <th className="px-4 py-2.5 font-medium">
                      <button
                        type="button"
                        onClick={() => toggleSort("total_files")}
                        className="inline-flex items-center gap-1 font-medium hover:text-foreground"
                        aria-label="Sort by file count"
                      >
                        Files {sortIcon("total_files")}
                      </button>
                    </th>
                    <th className="px-4 py-2.5 font-medium">Status</th>
                    <th className="min-w-32 px-4 py-2.5 font-medium">
                      <button
                        type="button"
                        onClick={() => toggleSort("progress")}
                        className="inline-flex items-center gap-1 font-medium hover:text-foreground"
                        aria-label="Sort by progress"
                      >
                        Progress {sortIcon("progress")}
                      </button>
                    </th>
                    <th className="px-4 py-2.5 font-medium">Confidence</th>
                    <th className="px-4 py-2.5 font-medium">Duration</th>
                    <th className="px-4 py-2.5 text-right font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {sorted.map((job, index) => {
                    const metrics = byBatchId.get(job.batch_id);
                    return (
                      <motion.tr
                        key={job.id}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ duration: 0.15, delay: index * 0.02 }}
                        className="border-b border-border/60 last:border-0 hover:bg-accent/30"
                      >
                        <td className="px-4 py-3">
                          <Link
                            href={ROUTES.batchDetail(job.batch_id)}
                            className="font-mono text-xs underline-offset-4 hover:underline"
                          >
                            {shortId(job.batch_id)}
                          </Link>
                        </td>
                        <td className="whitespace-nowrap px-4 py-3 text-xs text-muted-foreground">
                          {formatDateTime(job.created_at)}
                        </td>
                        <td className="px-4 py-3 font-mono text-xs tabular-nums text-muted-foreground">
                          {job.processed_files}/{job.total_files}
                          {job.failed_files > 0 ? (
                            <span className="text-destructive">
                              {" "}
                              (+{job.failed_files})
                            </span>
                          ) : null}
                        </td>
                        <td className="px-4 py-3">
                          <StatusBadge status={job.status} />
                        </td>
                        <td className="px-4 py-3">
                          <ProgressBar value={job.progress} failed={job.failed_files} />
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
                            <Button
                              size="icon"
                              variant="ghost"
                              aria-label="Preview batch"
                              title="Preview"
                              onClick={() =>
                                openDrawer({
                                  kind: "batch",
                                  id: job.batch_id,
                                  title: `Batch ${shortId(job.batch_id)}`,
                                })
                              }
                            >
                              <Eye />
                            </Button>
                            <Link
                              href={ROUTES.batchDetail(job.batch_id)}
                              aria-label="Open batch"
                              className="inline-flex h-8 items-center rounded-md border border-border px-2.5 text-xs font-medium transition-colors hover:bg-accent"
                            >
                              Open
                            </Link>
                            <ExportButtons
                              batchId={job.batch_id}
                              pending={exports.pending}
                              onCsv={exports.exportCsv}
                              onJson={exports.exportJson}
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

      {!jobsQuery.isLoading && !jobsQuery.isError && total > 0 ? (
        <Pagination
          page={page}
          pageSize={PAGE_SIZE}
          total={total}
          onPageChange={setPage}
        />
      ) : null}
    </PageContainer>
  );
}

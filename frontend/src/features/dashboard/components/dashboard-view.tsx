"use client";

import { RefreshCw, Upload } from "lucide-react";
import Link from "next/link";

import { ErrorState, HealthBadge } from "@/components/common";
import { PageContainer, PageHeader } from "@/components/layout";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ROUTES } from "@/lib/constants";

import {
  aggregateJobs,
  MetricsRow,
} from "@/features/dashboard/components/metrics-row";
import { RecentBatchesTable } from "@/features/dashboard/components/recent-batches-table";
import {
  useBackendHealth,
  useBatchMetricsForJobs,
  useJobsList,
  useSystemMetrics,
} from "@/features/dashboard/api";
import { useExportActions } from "@/features/shared/export-actions";

const RECENT_LIMIT = 8;
const AGGREGATE_LIMIT = 100;

export function DashboardView() {
  const jobsQuery = useJobsList({ limit: AGGREGATE_LIMIT });
  const systemQuery = useSystemMetrics();
  const healthQuery = useBackendHealth();
  const jobs = jobsQuery.data?.items ?? [];
  const { byBatchId } = useBatchMetricsForJobs(jobs);
  const exports = useExportActions();

  const metrics = jobsQuery.data
    ? aggregateJobs(jobs, byBatchId)
    : null;

  const refreshing =
    jobsQuery.isRefetching || systemQuery.isRefetching;

  const healthStatus = healthQuery.isError
    ? "unhealthy"
    : (healthQuery.data?.status ?? "unhealthy");

  return (
    <PageContainer>
      <PageHeader
        title="Dashboard"
        description="Platform throughput, batch health, and worker fleet at a glance."
        actions={
          <>
            <Badge variant="outline" className="font-mono">
              {healthQuery.data?.environment ?? "unknown"}
            </Badge>
            <HealthBadge
              status={healthStatus}
              label={
                healthQuery.data ? `v${healthQuery.data.version}` : "offline"
              }
            />
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                void jobsQuery.refetch();
                void systemQuery.refetch();
                void healthQuery.refetch();
              }}
              disabled={refreshing}
              aria-label="Refresh dashboard"
            >
              <RefreshCw className={refreshing ? "animate-spin" : undefined} />
              Refresh
            </Button>
            <Link href={ROUTES.upload}>
              <Button size="sm">
                <Upload />
                Quick Upload
              </Button>
            </Link>
          </>
        }
      />

      {jobsQuery.isError ? (
        <ErrorState
          error={jobsQuery.error}
          title="Failed to load jobs"
          onRetry={() => void jobsQuery.refetch()}
        />
      ) : (
        <>
          <MetricsRow
            metrics={metrics}
            workerCount={systemQuery.data?.worker_count ?? null}
            loading={jobsQuery.isLoading}
          />
          <RecentBatchesTable
            jobs={jobs.slice(0, RECENT_LIMIT)}
            metricsByBatchId={byBatchId}
            loading={jobsQuery.isLoading}
            pending={exports.pending}
            onExportCsv={exports.exportCsv}
            onExportJson={exports.exportJson}
          />
        </>
      )}
    </PageContainer>
  );
}

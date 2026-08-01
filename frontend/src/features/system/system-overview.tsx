"use client";

import { RefreshCw, Upload } from "lucide-react";
import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";

import {
  EmptyState,
  EmptyStateAction,
  ErrorState,
  HealthBadge,
  MetricCard,
  QuickActions,
  StatusBadge,
} from "@/components/common";
import { PageContainer, PageHeader } from "@/components/layout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { systemKeys } from "@/features/system";
import { ROUTES, SYSTEM_METRICS_REFETCH_MS } from "@/lib/constants";
import { formatDateTime } from "@/lib/format";
import {
  getHealth,
  getReadiness,
  getSystemMetrics,
  getSystemWorkers,
} from "@/services/system";

function ComponentRow({
  label,
  ok,
}: {
  label: string;
  ok: boolean | undefined;
}) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-border/60 py-2.5 last:border-0">
      <span className="text-sm text-foreground">{label}</span>
      <StatusBadge status={ok ? "COMPLETED" : "FAILED"} />
    </div>
  );
}

export function SystemOverview() {
  const healthQuery = useQuery({
    queryKey: systemKeys.list({ resource: "health" }),
    queryFn: getHealth,
    refetchInterval: SYSTEM_METRICS_REFETCH_MS,
    retry: 1,
  });
  const metricsQuery = useQuery({
    queryKey: systemKeys.metrics(),
    queryFn: getSystemMetrics,
    refetchInterval: SYSTEM_METRICS_REFETCH_MS,
  });
  const workersQuery = useQuery({
    queryKey: systemKeys.workers(),
    queryFn: getSystemWorkers,
    refetchInterval: SYSTEM_METRICS_REFETCH_MS,
  });
  const readyQuery = useQuery({
    queryKey: systemKeys.readiness(),
    queryFn: getReadiness,
    refetchInterval: SYSTEM_METRICS_REFETCH_MS,
    retry: false,
  });

  const refreshing =
    healthQuery.isFetching ||
    metricsQuery.isFetching ||
    workersQuery.isFetching;

  useEffect(() => {
    function onRefresh() {
      void healthQuery.refetch();
      void metricsQuery.refetch();
      void workersQuery.refetch();
      void readyQuery.refetch();
    }
    window.addEventListener("aip:refresh", onRefresh);
    return () => window.removeEventListener("aip:refresh", onRefresh);
  }, [healthQuery, metricsQuery, workersQuery, readyQuery]);

  const healthStatus = healthQuery.isError
    ? "unhealthy"
    : (healthQuery.data?.status ?? "unhealthy");

  const metrics = metricsQuery.data;
  const workers = workersQuery.data;

  return (
    <PageContainer className="max-w-5xl">
      <PageHeader
        title="System"
        description="Platform health, worker fleet, and dependency readiness."
        actions={
          <QuickActions
            actions={[
              {
                id: "refresh",
                label: "Refresh",
                icon: RefreshCw,
                shortcut: "R",
                disabled: refreshing,
                onClick: () => {
                  void healthQuery.refetch();
                  void metricsQuery.refetch();
                  void workersQuery.refetch();
                  void readyQuery.refetch();
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

      {healthQuery.isError && metricsQuery.isError ? (
        <ErrorState
          error={healthQuery.error}
          title="System endpoints unreachable"
          onRetry={() => {
            void healthQuery.refetch();
            void metricsQuery.refetch();
          }}
        />
      ) : (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center gap-2">
            <HealthBadge
              status={healthStatus}
              label={
                healthQuery.data
                  ? `API v${healthQuery.data.version}`
                  : "API offline"
              }
            />
            {healthQuery.data?.environment ? (
              <span className="rounded-md border border-border px-2 py-0.5 font-mono text-[11px] text-muted-foreground">
                {healthQuery.data.environment}
              </span>
            ) : null}
            {readyQuery.data ? (
              <span className="text-xs text-muted-foreground">
                Ready: {readyQuery.data.status === "healthy" ? "yes" : "no"}
              </span>
            ) : null}
          </div>

          {metricsQuery.isLoading ? (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" aria-busy>
              {Array.from({ length: 4 }, (_, i) => (
                <Skeleton key={i} className="h-24 w-full" />
              ))}
            </div>
          ) : metrics ? (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <MetricCard
                label="Workers"
                value={String(metrics.worker_count)}
                description={
                  workers
                    ? `${workers.stale_count} stale`
                    : "Active Celery workers"
                }
              />
              <MetricCard
                label="Version"
                value={metrics.system_version}
                description="Platform build"
              />
              <MetricCard
                label="Model"
                value={metrics.model_loaded ? "Loaded" : "Cold"}
                description="Inference readiness"
              />
              <MetricCard
                label="Checked"
                value={formatDateTime(metrics.checked_at)}
                description="Last metrics probe"
              />
            </div>
          ) : (
            <EmptyState
              title="Metrics unavailable"
              description="The metrics endpoint did not respond. Confirm the backend is running."
              action={
                <EmptyStateAction
                  label="Retry"
                  onClick={() => void metricsQuery.refetch()}
                />
              }
              hint="Ctrl+K → System"
            />
          )}

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Dependencies</CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                {metrics ? (
                  <div>
                    <ComponentRow label="Database" ok={metrics.database} />
                    <ComponentRow label="Redis" ok={metrics.redis} />
                    <ComponentRow label="Object storage (R2)" ok={metrics.r2} />
                    <ComponentRow label="Celery" ok={metrics.celery} />
                  </div>
                ) : (
                  <Skeleton className="h-32 w-full" />
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Workers</CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                {workersQuery.isLoading ? (
                  <Skeleton className="h-32 w-full" />
                ) : !workers || workers.workers.length === 0 ? (
                  <EmptyState
                    className="py-8"
                    title="No workers registered"
                    description="Start a Celery worker container to process upload jobs."
                    hint="docker compose up worker"
                  />
                ) : (
                  <ul className="divide-y divide-border">
                    {workers.workers.map((worker) => (
                      <li
                        key={worker.worker_id}
                        className="flex items-center justify-between gap-3 py-2.5"
                      >
                        <div className="min-w-0">
                          <p className="truncate font-mono text-xs">
                            {worker.worker_id}
                          </p>
                          <p className="text-[11px] text-muted-foreground">
                            {worker.last_heartbeat
                              ? formatDateTime(worker.last_heartbeat)
                              : "No heartbeat"}
                          </p>
                        </div>
                        <StatusBadge
                          status={worker.stale ? "FAILED" : "RUNNING"}
                        />
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </PageContainer>
  );
}

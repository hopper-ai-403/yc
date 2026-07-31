"use client";

import {
  Activity,
  CheckCircle2,
  FolderKanban,
  Gauge,
  Loader2,
  Sigma,
  Timer,
  XCircle,
} from "lucide-react";
import { motion } from "framer-motion";

import { MetricCard } from "@/components/common";
import {
  formatConfidence,
  formatDurationMs,
  formatPercent,
} from "@/lib/format";
import type { BatchMetricsRead, JobRead } from "@/types/domain";

interface DashboardMetrics {
  total: number;
  running: number;
  completed: number;
  failed: number;
  successRate: number | null;
  averageConfidence: number | null;
  averageProcessingMs: number | null;
}

export function aggregateJobs(
  jobs: JobRead[],
  metricsByBatchId: Map<string, BatchMetricsRead>,
): DashboardMetrics {
  let running = 0;
  let completed = 0;
  let failed = 0;
  let processed = 0;
  let failedFiles = 0;

  for (const job of jobs) {
    if (job.status === "RUNNING" || job.status === "QUEUED") running += 1;
    if (job.status === "COMPLETED") completed += 1;
    if (job.status === "FAILED") failed += 1;
    processed += job.processed_files;
    failedFiles += job.failed_files;
  }

  const metrics = [...metricsByBatchId.values()];
  const confidences = metrics
    .map((m) => m.average_confidence)
    .filter((v): v is number => v !== null);
  const durations = metrics
    .map((m) => m.average_processing_time_ms)
    .filter((v): v is number => v !== null);

  const totalFiles = processed + failedFiles;

  return {
    total: jobs.length,
    running,
    completed,
    failed,
    successRate: totalFiles > 0 ? processed / totalFiles : null,
    averageConfidence:
      confidences.length > 0
        ? confidences.reduce((a, b) => a + b, 0) / confidences.length
        : null,
    averageProcessingMs:
      durations.length > 0
        ? durations.reduce((a, b) => a + b, 0) / durations.length
        : null,
  };
}

interface MetricsRowProps {
  metrics: DashboardMetrics | null;
  workerCount: number | null;
  loading: boolean;
}

export function MetricsRow({ metrics, workerCount, loading }: MetricsRowProps) {
  const cards = [
    {
      label: "Total Batches",
      value: metrics?.total ?? 0,
      icon: FolderKanban,
      description: "All time",
    },
    {
      label: "Running Jobs",
      value: metrics?.running ?? 0,
      icon: Loader2,
      description: "Queued + processing",
    },
    {
      label: "Completed Jobs",
      value: metrics?.completed ?? 0,
      icon: CheckCircle2,
      description: "Finished successfully",
    },
    {
      label: "Failed Jobs",
      value: metrics?.failed ?? 0,
      icon: XCircle,
      description: "Require attention",
    },
    {
      label: "Avg Confidence",
      value: formatConfidence(metrics?.averageConfidence),
      icon: Sigma,
      description: "Across completed batches",
    },
    {
      label: "Avg Processing",
      value: formatDurationMs(metrics?.averageProcessingMs),
      icon: Timer,
      description: "Per audio file",
    },
    {
      label: "Success Rate",
      value: formatPercent(metrics?.successRate),
      icon: Gauge,
      description: "Processed vs failed files",
    },
    {
      label: "Workers",
      value: workerCount ?? "—",
      icon: Activity,
      description: "Active Celery workers",
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      {cards.map((card, index) => (
        <motion.div
          key={card.label}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2, delay: index * 0.03 }}
        >
          <MetricCard
            label={card.label}
            value={card.value}
            description={card.description}
            icon={card.icon}
            loading={loading}
          />
        </motion.div>
      ))}
    </div>
  );
}

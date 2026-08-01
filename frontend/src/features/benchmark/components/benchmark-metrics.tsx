"use client";

import {
  Activity,
  Gauge,
  Percent,
  Sigma,
  Timer,
  TrendingDown,
  TrendingUp,
  XCircle,
  Zap,
} from "lucide-react";
import { motion } from "framer-motion";

import { MetricCard } from "@/components/common";
import {
  formatConfidence,
  formatDurationMs,
  formatPercent,
} from "@/lib/format";
import type { BenchmarkRead } from "@/types/domain";

interface BenchmarkMetricsProps {
  benchmark: BenchmarkRead | null;
  workerCount: number | null;
  loading: boolean;
}

export function BenchmarkMetrics({
  benchmark,
  workerCount,
  loading,
}: BenchmarkMetricsProps) {
  const successRate =
    benchmark && benchmark.total_files > 0
      ? benchmark.successful_files / benchmark.total_files
      : null;

  const cards = [
    {
      label: "Average Latency",
      value: formatDurationMs(benchmark?.average_latency_ms),
      icon: Timer,
      description: "Per-file pipeline",
    },
    {
      label: "P50",
      value: formatDurationMs(benchmark?.p50_latency_ms),
      icon: Gauge,
      description: "Median latency",
    },
    {
      label: "P95",
      value: formatDurationMs(benchmark?.p95_latency_ms),
      icon: TrendingUp,
      description: "95th percentile",
    },
    {
      label: "P99",
      value: formatDurationMs(benchmark?.p99_latency_ms),
      icon: Zap,
      description: "99th percentile",
    },
    {
      label: "Throughput",
      value:
        benchmark?.throughput_files_per_minute != null
          ? `${benchmark.throughput_files_per_minute}/min`
          : "—",
      icon: Activity,
      description: "Files per minute",
    },
    {
      label: "Avg Confidence",
      value: formatConfidence(benchmark?.average_confidence),
      icon: Sigma,
      description: "Across predictions",
    },
    {
      label: "Success Rate",
      value: formatPercent(successRate),
      icon: Percent,
      description: `${benchmark?.successful_files ?? 0}/${benchmark?.total_files ?? 0} files`,
    },
    {
      label: "Failure Rate",
      value: formatPercent(benchmark?.failure_rate ?? null),
      icon: XCircle,
      description: "Failed files",
    },
    {
      label: "Workers",
      value: workerCount ?? "—",
      icon: TrendingDown,
      description: "Active Celery workers",
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
      {cards.map((card, index) => (
        <motion.div
          key={card.label}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.18, delay: index * 0.02 }}
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

"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { memo } from "react";

import {
  CHART_COLORS,
  chartAxisTick,
  chartTooltipStyle,
} from "@/lib/chart-theme";
import { formatDurationMs } from "@/lib/format";
import type { StageStats } from "@/features/benchmark/lib/aggregations";

export const LatencyStackedChart = memo(function LatencyStackedChart({
  stats,
}: {
  stats: StageStats[];
}) {
  const stages = stats.filter((stage) => stage.stage !== "total");
  const data = [
    Object.fromEntries([
      ["name", "Avg"],
      ...stages.map((stage) => [stage.label, Math.round(stage.average)]),
    ]),
  ];

  if (stages.every((stage) => stage.average === 0)) {
    return (
      <p className="py-8 text-center text-xs text-muted-foreground">
        No per-stage timing samples available for this batch.
      </p>
    );
  }

  return (
    <div className="h-24 w-full" role="img" aria-label="Stacked latency by pipeline stage">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ left: 8, right: 8, top: 8, bottom: 8 }}>
          <XAxis type="number" hide />
          <YAxis type="category" dataKey="name" hide />
          <Tooltip
            contentStyle={chartTooltipStyle}
            formatter={(value) => formatDurationMs(Number(value))}
          />
          {stages.map((stage, index) => (
            <Bar
              key={stage.stage}
              dataKey={stage.label}
              stackId="latency"
              fill={CHART_COLORS.series[index % CHART_COLORS.series.length]}
              radius={index === stages.length - 1 ? [0, 4, 4, 0] : 0}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
});

export const ConfidenceHistogram = memo(function ConfidenceHistogram({
  data,
}: {
  data: Array<{ bucket: string; count: number }>;
}) {
  if (data.every((item) => item.count === 0)) {
    return (
      <p className="py-8 text-center text-xs text-muted-foreground">
        No confidence values to chart.
      </p>
    );
  }

  return (
    <div className="h-48 w-full" role="img" aria-label="Confidence distribution histogram">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ left: 0, right: 8, top: 8, bottom: 0 }}>
          <CartesianGrid stroke={CHART_COLORS.border} vertical={false} strokeDasharray="3 3" />
          <XAxis dataKey="bucket" tick={chartAxisTick} interval={1} />
          <YAxis allowDecimals={false} tick={chartAxisTick} width={28} />
          <Tooltip contentStyle={chartTooltipStyle} />
          <Bar dataKey="count" fill={CHART_COLORS.info} radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
});

export const DistributionBarChart = memo(function DistributionBarChart({
  data,
  label,
}: {
  data: Array<{ name: string; value: number }>;
  label: string;
}) {
  if (data.length === 0) {
    return (
      <p className="py-8 text-center text-xs text-muted-foreground">No data.</p>
    );
  }

  return (
    <div className="h-48 w-full" role="img" aria-label={label}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          layout="vertical"
          margin={{ left: 8, right: 16, top: 8, bottom: 8 }}
        >
          <CartesianGrid stroke={CHART_COLORS.border} horizontal={false} strokeDasharray="3 3" />
          <XAxis type="number" allowDecimals={false} tick={chartAxisTick} />
          <YAxis
            type="category"
            dataKey="name"
            width={110}
            tick={chartAxisTick}
            tickFormatter={(value: string) =>
              value.length > 14 ? `${value.slice(0, 12)}…` : value
            }
          />
          <Tooltip contentStyle={chartTooltipStyle} />
          <Bar dataKey="value" radius={[0, 4, 4, 0]}>
            {data.map((_, index) => (
              <Cell
                key={index}
                fill={CHART_COLORS.series[index % CHART_COLORS.series.length]}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
});

export const DistributionPieChart = memo(function DistributionPieChart({
  data,
  label,
}: {
  data: Array<{ name: string; value: number }>;
  label: string;
}) {
  if (data.length === 0) {
    return (
      <p className="py-8 text-center text-xs text-muted-foreground">No data.</p>
    );
  }

  return (
    <div className="h-48 w-full" role="img" aria-label={label}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            nameKey="name"
            innerRadius={42}
            outerRadius={68}
            paddingAngle={2}
            stroke="hsl(var(--card))"
          >
            {data.map((_, index) => (
              <Cell
                key={index}
                fill={CHART_COLORS.series[index % CHART_COLORS.series.length]}
              />
            ))}
          </Pie>
          <Tooltip contentStyle={chartTooltipStyle} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
});

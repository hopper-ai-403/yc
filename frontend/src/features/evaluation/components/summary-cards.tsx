"use client";

import {
  CheckCircle2,
  Percent,
  Sigma,
  Target,
} from "lucide-react";
import { motion } from "framer-motion";

import { MetricCard } from "@/components/common";
import { formatConfidence, formatPercent } from "@/lib/format";
import type { EvaluationSummary } from "@/features/evaluation/lib/compare";
import { ASSESSMENT_FIELDS } from "@/lib/constants";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function EvaluationSummaryCards({
  summary,
}: {
  summary: EvaluationSummary | null;
}) {
  const cards = [
    {
      label: "Overall Accuracy",
      value: formatPercent(summary?.overallAccuracy ?? null),
      icon: Target,
      description: `${summary?.matched ?? 0} exact matches`,
    },
    {
      label: "Agreement",
      value: formatPercent(summary?.agreement ?? null),
      icon: CheckCircle2,
      description: "Exact + close",
    },
    {
      label: "Per-field Avg",
      value: formatPercent(
        summary
          ? Object.values(summary.perFieldAccuracy).reduce((a, b) => a + b, 0) /
              ASSESSMENT_FIELDS.length
          : null,
      ),
      icon: Percent,
      description: "Mean field accuracy",
    },
    {
      label: "Avg Confidence",
      value: formatConfidence(summary?.averageConfidence ?? null),
      icon: Sigma,
      description: "On actual predictions",
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {cards.map((card, index) => (
        <motion.div
          key={card.label}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.18, delay: index * 0.03 }}
        >
          <MetricCard
            label={card.label}
            value={card.value}
            description={card.description}
            icon={card.icon}
            loading={!summary}
          />
        </motion.div>
      ))}
    </div>
  );
}

export function PerFieldAccuracyTable({
  summary,
}: {
  summary: EvaluationSummary;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Per-field Accuracy</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted-foreground">
                <th className="px-4 py-2.5 font-medium">Field</th>
                <th className="px-4 py-2.5 font-medium">Accuracy</th>
                <th className="min-w-40 px-4 py-2.5 font-medium">Bar</th>
              </tr>
            </thead>
            <tbody>
              {ASSESSMENT_FIELDS.map((field) => {
                const value = summary.perFieldAccuracy[field];
                return (
                  <tr
                    key={field}
                    className="border-b border-border/60 last:border-0"
                  >
                    <td className="px-4 py-2.5 font-mono text-xs">{field}</td>
                    <td className="px-4 py-2.5 font-mono text-xs tabular-nums">
                      {formatPercent(value)}
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                        <div
                          className="h-full rounded-full bg-success"
                          style={{ width: `${Math.round(value * 100)}%` }}
                        />
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

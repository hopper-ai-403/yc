"use client";

import { memo } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export const ConfusionMatrix = memo(function ConfusionMatrix({
  labels,
  matrix,
}: {
  labels: string[];
  matrix: number[][];
}) {
  if (labels.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Emotion Confusion Matrix</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="py-6 text-center text-xs text-muted-foreground">
            Not enough overlapping labels to build a matrix.
          </p>
        </CardContent>
      </Card>
    );
  }

  const max = Math.max(1, ...matrix.flat());

  return (
    <Card>
      <CardHeader>
        <CardTitle>Emotion Confusion Matrix</CardTitle>
        <p className="text-xs text-muted-foreground">
          Rows = expected · Columns = actual
        </p>
      </CardHeader>
      <CardContent className="overflow-x-auto">
        <table className="w-full min-w-max border-collapse text-xs" aria-label="Emotion confusion matrix">
          <thead>
            <tr>
              <th className="px-2 py-1.5 text-left font-medium text-muted-foreground">
                Exp ↓ / Act →
              </th>
              {labels.map((label) => (
                <th
                  key={label}
                  className="px-2 py-1.5 text-center font-mono font-medium text-muted-foreground"
                >
                  {label.slice(0, 3)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {labels.map((rowLabel, rowIndex) => (
              <tr key={rowLabel}>
                <th className="whitespace-nowrap px-2 py-1.5 text-left font-mono font-medium text-muted-foreground">
                  {rowLabel}
                </th>
                {matrix[rowIndex].map((value, colIndex) => {
                  const intensity = value / max;
                  const diagonal = rowIndex === colIndex;
                  return (
                    <td key={`${rowIndex}-${colIndex}`} className="p-1">
                      <div
                        className={cn(
                          "flex h-9 w-9 items-center justify-center rounded-md font-mono tabular-nums",
                          diagonal
                            ? "ring-1 ring-success/40"
                            : "ring-1 ring-border/60",
                        )}
                        style={{
                          backgroundColor: `hsl(var(--${diagonal ? "success" : "info"}) / ${0.08 + intensity * 0.45})`,
                        }}
                        title={`${rowLabel} → ${labels[colIndex]}: ${value}`}
                      >
                        {value}
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
});

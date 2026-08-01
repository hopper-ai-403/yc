"use client";

import { CopyButton, JsonViewer } from "@/components/common";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { RowComparison } from "@/features/evaluation/lib/compare";

export function JsonComparison({ row }: { row: RowComparison | null }) {
  if (!row) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>JSON Comparison</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="py-6 text-center text-xs text-muted-foreground">
            Select a row to inspect expected vs actual JSON.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>JSON Comparison · {row.filename}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <p className="text-xs font-medium text-muted-foreground">Expected</p>
              {row.expected ? (
                <CopyButton
                  value={JSON.stringify(row.expected, null, 2)}
                  size="icon"
                  className="size-7"
                />
              ) : null}
            </div>
            {row.expected ? (
              <JsonViewer data={row.expected} defaultOpenDepth={2} className="max-h-80" />
            ) : (
              <p className="rounded-md border border-dashed border-border p-4 text-xs text-muted-foreground">
                No expected label for this file.
              </p>
            )}
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <p className="text-xs font-medium text-muted-foreground">Actual</p>
              {row.actual ? (
                <CopyButton
                  value={JSON.stringify(row.actual, null, 2)}
                  size="icon"
                  className="size-7"
                />
              ) : null}
            </div>
            {row.actual ? (
              <JsonViewer data={row.actual} defaultOpenDepth={2} className="max-h-80" />
            ) : (
              <p className="rounded-md border border-dashed border-border p-4 text-xs text-muted-foreground">
                No prediction produced for this file.
              </p>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

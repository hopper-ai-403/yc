"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type {
  FieldComparison,
  MatchKind,
  RowComparison,
} from "@/features/evaluation/lib/compare";
import { cn } from "@/lib/utils";
import { formatConfidence } from "@/lib/format";

const MATCH_STYLES: Record<MatchKind, string> = {
  exact: "bg-success/15 text-success",
  close: "bg-warning/15 text-warning",
  mismatch: "bg-destructive/15 text-destructive",
  missing: "bg-muted text-muted-foreground",
};

function MatchCell({ field }: { field: FieldComparison }) {
  return (
    <td className="px-2 py-2">
      <div
        className={cn(
          "rounded-md px-1.5 py-1 text-center font-mono text-[10px] tabular-nums",
          MATCH_STYLES[field.match],
        )}
        title={`expected ${String(field.expected)} · actual ${String(field.actual)}`}
      >
        {field.actual === undefined ? "—" : String(field.actual)}
      </div>
    </td>
  );
}

const FIELD_HEADERS = [
  { key: "emotional_tone", label: "Emotion" },
  { key: "emotional_intensity", label: "Intensity" },
  { key: "background_noise_present", label: "Noise?" },
  { key: "background_noise_type", label: "Type" },
  { key: "background_noise_severity", label: "Severity" },
  { key: "audio_quality", label: "Quality" },
  { key: "speaker_overlap_present", label: "Overlap" },
  { key: "long_silence_present", label: "Silence" },
  { key: "confidence", label: "Conf" },
] as const;

interface ComparisonTableProps {
  rows: RowComparison[];
  selected: string | null;
  onSelect: (filename: string) => void;
}

export function ComparisonTable({
  rows,
  selected,
  onSelect,
}: ComparisonTableProps) {
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle>Comparison</CardTitle>
        <div className="flex gap-1.5 text-[10px]">
          <Badge className={MATCH_STYLES.exact}>Exact</Badge>
          <Badge className={MATCH_STYLES.close}>Close</Badge>
          <Badge className={MATCH_STYLES.mismatch}>Mismatch</Badge>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        {rows.length === 0 ? (
          <p className="p-6 text-center text-xs text-muted-foreground">
            No rows match the current filters.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[960px] text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted-foreground">
                  <th className="px-4 py-2.5 font-medium">Filename</th>
                  <th className="px-3 py-2.5 font-medium">Match</th>
                  {FIELD_HEADERS.map((header) => (
                    <th key={header.key} className="px-2 py-2.5 font-medium">
                      {header.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr
                    key={row.filename}
                    className={cn(
                      "cursor-pointer border-b border-border/60 last:border-0 hover:bg-accent/30",
                      selected === row.filename && "bg-accent/40",
                    )}
                    onClick={() => onSelect(row.filename)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        onSelect(row.filename);
                      }
                    }}
                    tabIndex={0}
                    aria-selected={selected === row.filename}
                  >
                    <td className="max-w-48 truncate px-4 py-2.5 font-mono text-xs">
                      {row.filename}
                    </td>
                    <td className="px-3 py-2.5">
                      <Badge className={MATCH_STYLES[row.overall]}>
                        {row.overall}
                      </Badge>
                      {row.confidence !== null ? (
                        <span className="ml-1 font-mono text-[10px] text-muted-foreground">
                          {formatConfidence(row.confidence)}
                        </span>
                      ) : null}
                    </td>
                    {FIELD_HEADERS.map((header) => {
                      const field = row.fields.find(
                        (item) => item.field === header.key,
                      )!;
                      return <MatchCell key={header.key} field={field} />;
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

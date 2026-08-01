"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { shortId } from "@/features/dashboard/components/recent-batches-table";
import { formatDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { JobRead } from "@/types/domain";

interface BatchSelectorProps {
  jobs: JobRead[];
  value: string | null;
  onChange: (batchId: string) => void;
  loading?: boolean;
}

export function BatchSelector({
  jobs,
  value,
  onChange,
  loading = false,
}: BatchSelectorProps) {
  if (loading) {
    return (
      <div className="flex gap-2 overflow-x-auto" aria-busy="true">
        {Array.from({ length: 4 }, (_, index) => (
          <div key={index} className="h-8 w-28 animate-pulse rounded-md bg-muted" />
        ))}
      </div>
    );
  }

  if (jobs.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">
        No completed batches yet. Run an evaluation batch to unlock benchmarks.
      </p>
    );
  }

  return (
    <div
      className="flex flex-wrap gap-1.5"
      role="listbox"
      aria-label="Select batch for benchmarking"
    >
      {jobs.map((job) => {
        const selected = value === job.batch_id;
        return (
          <Button
            key={job.id}
            size="sm"
            variant={selected ? "secondary" : "ghost"}
            role="option"
            aria-selected={selected}
            onClick={() => onChange(job.batch_id)}
            className={cn("font-mono", selected && "ring-1 ring-ring")}
          >
            {shortId(job.batch_id)}
            <Badge variant="muted" className="ml-1 font-sans">
              {job.total_files}
            </Badge>
            <span className="hidden font-sans text-[10px] text-muted-foreground sm:inline">
              {formatDateTime(job.completed_at ?? job.created_at)}
            </span>
          </Button>
        );
      })}
    </div>
  );
}

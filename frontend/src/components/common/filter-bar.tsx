"use client";

import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface FilterOption {
  value: string;
  label: string;
}

interface FilterBarProps {
  options: FilterOption[];
  value: string | null;
  onChange: (value: string | null) => void;
  allLabel?: string;
  trailing?: ReactNode;
  className?: string;
}

/** Horizontal chip filter; null value = no filter. */
export function FilterBar({
  options,
  value,
  onChange,
  allLabel = "All",
  trailing,
  className,
}: FilterBarProps) {
  return (
    <div className={cn("flex flex-wrap items-center gap-1.5", className)}>
      <Button
        size="sm"
        variant={value === null ? "secondary" : "ghost"}
        onClick={() => onChange(null)}
      >
        {allLabel}
      </Button>
      {options.map((option) => (
        <Button
          key={option.value}
          size="sm"
          variant={value === option.value ? "secondary" : "ghost"}
          onClick={() =>
            onChange(value === option.value ? null : option.value)
          }
        >
          {option.label}
        </Button>
      ))}
      {trailing ? <div className="ml-auto">{trailing}</div> : null}
    </div>
  );
}

export function FilterCount({ count }: { count: number }) {
  return (
    <Badge variant="muted" className="font-mono">
      {count}
    </Badge>
  );
}

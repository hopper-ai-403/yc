"use client";

import { ChevronRight } from "lucide-react";
import { useState, type ReactNode } from "react";

import { cn } from "@/lib/utils";

function JsonLeaf({ value }: { value: unknown }) {
  if (value === null) return <span className="text-muted-foreground">null</span>;
  switch (typeof value) {
    case "string":
      return <span className="text-success">&quot;{value}&quot;</span>;
    case "number":
      return <span className="text-info">{value}</span>;
    case "boolean":
      return <span className="text-warning">{String(value)}</span>;
    default:
      return <span className="text-muted-foreground">{String(value)}</span>;
  }
}

function JsonNode({
  name,
  value,
  depth,
  defaultOpenDepth,
}: {
  name?: string;
  value: unknown;
  depth: number;
  defaultOpenDepth: number;
}): ReactNode {
  const [open, setOpen] = useState(depth < defaultOpenDepth);

  const isObject = typeof value === "object" && value !== null;
  if (!isObject) {
    return (
      <div className="flex gap-2">
        {name !== undefined ? (
          <span className="text-foreground">{name}:</span>
        ) : null}
        <JsonLeaf value={value} />
      </div>
    );
  }

  const entries = Array.isArray(value)
    ? value.map((item, index) => [String(index), item] as const)
    : Object.entries(value as Record<string, unknown>);
  const preview = Array.isArray(value) ? `[${entries.length}]` : `{${entries.length}}`;

  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="flex items-center gap-1 text-left hover:text-foreground"
      >
        <ChevronRight
          className={cn(
            "size-3 shrink-0 text-muted-foreground transition-transform",
            open && "rotate-90",
          )}
        />
        {name !== undefined ? (
          <span className="text-foreground">{name}:</span>
        ) : null}
        {!open ? (
          <span className="text-muted-foreground">{preview}</span>
        ) : null}
      </button>
      {open ? (
        <div className="ml-3 border-l border-border pl-3">
          {entries.map(([key, item]) => (
            <JsonNode
              key={key}
              name={key}
              value={item}
              depth={depth + 1}
              defaultOpenDepth={defaultOpenDepth}
            />
          ))}
          <span className="text-muted-foreground">
            {Array.isArray(value) ? "]" : "}"}
          </span>
        </div>
      ) : null}
    </div>
  );
}

export function JsonViewer({
  data,
  defaultOpenDepth = 1,
  className,
}: {
  data: unknown;
  defaultOpenDepth?: number;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "scrollbar-thin overflow-auto rounded-md border border-border bg-muted/30 p-3 font-mono text-xs leading-5 text-muted-foreground",
        className,
      )}
    >
      <JsonNode value={data} depth={0} defaultOpenDepth={defaultOpenDepth} />
    </div>
  );
}

import { CheckCircle2, Circle, Loader2, XCircle } from "lucide-react";

import { cn } from "@/lib/utils";

export type TimelineItemStatus = "completed" | "active" | "failed" | "pending";

export interface TimelineItem {
  id: string;
  label: string;
  description?: string;
  timestamp?: string;
  status: TimelineItemStatus;
}

const ICONS: Record<TimelineItemStatus, typeof Circle> = {
  completed: CheckCircle2,
  active: Loader2,
  failed: XCircle,
  pending: Circle,
};

const COLORS: Record<TimelineItemStatus, string> = {
  completed: "text-success",
  active: "text-info",
  failed: "text-destructive",
  pending: "text-muted-foreground/50",
};

export function Timeline({
  items,
  className,
}: {
  items: TimelineItem[];
  className?: string;
}) {
  return (
    <ol className={cn("relative space-y-0", className)}>
      {items.map((item, index) => {
        const Icon = ICONS[item.status];
        const last = index === items.length - 1;
        return (
          <li key={item.id} className="relative flex gap-3 pb-5 last:pb-0">
            {!last ? (
              <span
                aria-hidden
                className="absolute left-[7px] top-5 h-full w-px bg-border"
              />
            ) : null}
            <Icon
              className={cn(
                "mt-0.5 size-4 shrink-0",
                COLORS[item.status],
                item.status === "active" && "animate-spin",
              )}
            />
            <div className="min-w-0 flex-1">
              <div className="flex items-baseline justify-between gap-2">
                <p
                  className={cn(
                    "text-sm",
                    item.status === "pending"
                      ? "text-muted-foreground/60"
                      : "text-foreground",
                  )}
                >
                  {item.label}
                </p>
                {item.timestamp ? (
                  <span className="shrink-0 font-mono text-[10px] text-muted-foreground">
                    {item.timestamp}
                  </span>
                ) : null}
              </div>
              {item.description ? (
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {item.description}
                </p>
              ) : null}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

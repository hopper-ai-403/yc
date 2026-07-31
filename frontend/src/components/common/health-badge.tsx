import { cn } from "@/lib/utils";
import type { HealthState } from "@/types/domain";

const DOT_COLORS: Record<HealthState, string> = {
  healthy: "bg-success",
  degraded: "bg-warning",
  unhealthy: "bg-destructive",
};

export function HealthBadge({
  status,
  label,
  className,
}: {
  status: HealthState;
  label?: string;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 text-xs text-muted-foreground",
        className,
      )}
    >
      <span className="relative flex size-2">
        {status === "healthy" ? (
          <span
            className={cn(
              "absolute inline-flex h-full w-full animate-ping rounded-full opacity-40",
              DOT_COLORS[status],
            )}
          />
        ) : null}
        <span
          className={cn(
            "relative inline-flex size-2 rounded-full",
            DOT_COLORS[status],
          )}
        />
      </span>
      {label ?? status}
    </span>
  );
}

import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

interface MetricCardProps {
  label: string;
  value: ReactNode;
  description?: string;
  icon?: LucideIcon;
  trend?: { value: string; positive?: boolean };
  loading?: boolean;
  className?: string;
}

export function MetricCard({
  label,
  value,
  description,
  icon: Icon,
  trend,
  loading = false,
  className,
}: MetricCardProps) {
  return (
    <Card className={cn("overflow-hidden", className)}>
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 space-y-1">
            <p className="text-xs font-medium text-muted-foreground">{label}</p>
            {loading ? (
              <Skeleton className="h-7 w-20" />
            ) : (
              <p className="truncate text-2xl font-semibold tracking-tight text-foreground">
                {value}
              </p>
            )}
            {description && !loading ? (
              <p className="truncate text-xs text-muted-foreground">{description}</p>
            ) : null}
            {trend && !loading ? (
              <p
                className={cn(
                  "text-xs font-medium",
                  trend.positive === false ? "text-destructive" : "text-success",
                )}
              >
                {trend.value}
              </p>
            ) : null}
          </div>
          {Icon ? (
            <div className="rounded-md border border-border bg-muted/50 p-2">
              <Icon className="size-4 text-muted-foreground" />
            </div>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}

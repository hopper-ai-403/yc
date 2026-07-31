import {
  AlertCircle,
  CheckCircle2,
  Circle,
  Clock,
  Loader2,
  XCircle,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { AudioStatus, BatchStatus, HealthState, JobStatus } from "@/types/domain";

type StatusLike = JobStatus | AudioStatus | BatchStatus | HealthState | string;

const VARIANT_BY_STATUS: Record<
  string,
  "success" | "warning" | "destructive" | "info" | "muted" | "default"
> = {
  COMPLETED: "success",
  healthy: "success",
  RUNNING: "info",
  PROCESSING: "info",
  degraded: "warning",
  QUEUED: "warning",
  PENDING: "muted",
  UPLOADED: "muted",
  VALIDATED: "default",
  PROCESSED: "default",
  FAILED: "destructive",
  CANCELLED: "muted",
  unhealthy: "destructive",
};

const ICON_BY_STATUS: Record<string, typeof CheckCircle2> = {
  COMPLETED: CheckCircle2,
  healthy: CheckCircle2,
  RUNNING: Loader2,
  PROCESSING: Loader2,
  degraded: AlertCircle,
  QUEUED: Clock,
  PENDING: Circle,
  FAILED: XCircle,
  unhealthy: XCircle,
  CANCELLED: Circle,
};

interface StatusBadgeProps {
  status: StatusLike;
  label?: string;
  className?: string;
}

export function StatusBadge({ status, label, className }: StatusBadgeProps) {
  const key = String(status);
  const variant = VARIANT_BY_STATUS[key] ?? "default";
  const Icon = ICON_BY_STATUS[key] ?? Circle;
  const spinning = key === "RUNNING" || key === "PROCESSING";
  const text = label ?? key.charAt(0) + key.slice(1).toLowerCase();

  return (
    <Badge variant={variant} className={className}>
      <Icon className={spinning ? "animate-spin" : undefined} />
      {text}
    </Badge>
  );
}

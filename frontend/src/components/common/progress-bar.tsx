import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

interface ProgressBarProps {
  value: number;
  total?: number;
  showLabel?: boolean;
  failed?: number;
  className?: string;
}

export function ProgressBar({
  value,
  total,
  showLabel = true,
  failed = 0,
  className,
}: ProgressBarProps) {
  const percent =
    total !== undefined && total > 0
      ? Math.round((value / total) * 100)
      : Math.round(value);

  return (
    <div className={cn("flex items-center gap-3", className)}>
      <div className="relative flex-1">
        <Progress
          value={percent}
          indicatorClassName={
            failed > 0 && percent >= 100 ? "bg-warning" : undefined
          }
        />
      </div>
      {showLabel ? (
        <span className="w-10 text-right font-mono text-xs tabular-nums text-muted-foreground">
          {percent}%
        </span>
      ) : null}
    </div>
  );
}

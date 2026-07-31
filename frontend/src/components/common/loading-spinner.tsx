import { Loader2 } from "lucide-react";
import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

export function LoadingSpinner({
  className,
  ...props
}: ComponentProps<typeof Loader2>) {
  return (
    <Loader2
      aria-label="Loading"
      className={cn("size-4 animate-spin text-muted-foreground", className)}
      {...props}
    />
  );
}

export function LoadingBlock({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex h-32 w-full flex-col items-center justify-center gap-2 text-muted-foreground">
      <LoadingSpinner className="size-5" />
      <span className="text-xs">{label}</span>
    </div>
  );
}

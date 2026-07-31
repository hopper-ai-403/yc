"use client";

import { ServerCrash } from "lucide-react";
import { useEffect } from "react";

import { EmptyState } from "@/components/common/empty-state";
import { Button } from "@/components/ui/button";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[route-error]", error);
  }, [error]);

  return (
    <div className="mx-auto max-w-2xl px-6 pt-16">
      <EmptyState
        icon={ServerCrash}
        title="500 — Something went wrong"
        description="An unexpected error occurred while rendering this page."
        action={
          <Button size="sm" variant="outline" onClick={reset}>
            Try again
          </Button>
        }
      />
      {error.digest ? (
        <p className="mt-4 text-center font-mono text-[10px] text-muted-foreground">
          digest: {error.digest}
        </p>
      ) : null}
    </div>
  );
}

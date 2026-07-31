"use client";

import type { ReactNode } from "react";
import { Toaster } from "sonner";

export function ToastProvider(): ReactNode {
  return (
    <Toaster
      position="bottom-right"
      toastOptions={{
        classNames: {
          toast: "bg-card border-border text-card-foreground",
          description: "text-muted-foreground",
        },
      }}
    />
  );
}

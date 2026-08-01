"use client";

import type { ReactNode } from "react";
import { Toaster } from "sonner";

export function ToastProvider(): ReactNode {
  return (
    <Toaster
      position="bottom-right"
      closeButton
      richColors={false}
      expand={false}
      visibleToasts={4}
      gap={8}
      toastOptions={{
        duration: 4200,
        classNames: {
          toast:
            "group bg-card border border-border text-card-foreground shadow-lg",
          title: "text-sm font-medium",
          description: "text-xs text-muted-foreground",
          actionButton:
            "bg-secondary text-secondary-foreground text-xs font-medium",
          cancelButton: "bg-muted text-muted-foreground text-xs",
          closeButton: "border-border bg-card text-muted-foreground",
          success: "border-success/30",
          error: "border-destructive/30",
          loading: "border-info/30",
        },
      }}
    />
  );
}

"use client";

import { toast } from "sonner";

import { ROUTES } from "@/lib/constants";
import { useActivityStore } from "@/stores/activity-store";

type NotifyAction = {
  label: string;
  onClick: () => void;
};

function trackActivity(args: {
  id: string;
  kind: "upload" | "job" | "prediction" | "export" | "error" | "system";
  status: "running" | "success" | "failed" | "queued" | "info";
  title: string;
  description?: string;
  href?: string;
  progress?: number;
}) {
  useActivityStore.getState().push(args);
}

export const notify = {
  success(message: string, opts?: { description?: string; href?: string; id?: string }) {
    if (opts?.id) {
      trackActivity({
        id: opts.id,
        kind: "system",
        status: "success",
        title: message,
        description: opts.description,
        href: opts.href,
      });
    }
    toast.success(message, {
      description: opts?.description,
      action: opts?.href
        ? {
            label: "Open",
            onClick: () => {
              window.location.href = opts.href!;
            },
          }
        : undefined,
    });
  },

  error(
    message: string,
    opts?: { description?: string; onRetry?: () => void; id?: string },
  ) {
    if (opts?.id) {
      trackActivity({
        id: opts.id,
        kind: "error",
        status: "failed",
        title: message,
        description: opts.description,
      });
    }
    toast.error(message, {
      description: opts?.description,
      action: opts?.onRetry
        ? { label: "Retry", onClick: opts.onRetry }
        : undefined,
    });
  },

  progress(id: string, message: string, percent: number, description?: string) {
    trackActivity({
      id,
      kind: "upload",
      status: "running",
      title: message,
      description,
      progress: percent,
    });
    toast.loading(message, {
      id,
      description: description ?? `${percent}%`,
    });
  },

  dismiss(id: string) {
    toast.dismiss(id);
  },

  uploadStarted(id: string, fileCount: number) {
    trackActivity({
      id,
      kind: "upload",
      status: "running",
      title: "Uploading batch",
      description: `${fileCount} file${fileCount === 1 ? "" : "s"}`,
      progress: 0,
      href: ROUTES.upload,
    });
    toast.loading("Uploading batch…", { id, description: `${fileCount} files` });
  },

  uploadSuccess(id: string, batchId: string, files: number) {
    useActivityStore.getState().update(id, {
      status: "success",
      title: "Upload complete",
      description: `${files} files · ${batchId.slice(0, 8)}`,
      progress: 100,
      href: ROUTES.batchDetail(batchId),
    });
    toast.success("Upload complete", {
      id,
      description: `${files} files accepted`,
      action: {
        label: "Open batch",
        onClick: () => {
          window.location.href = ROUTES.batchDetail(batchId);
        },
      },
    });
  },

  uploadFailed(id: string, message: string, onRetry?: () => void) {
    useActivityStore.getState().update(id, {
      status: "failed",
      title: "Upload failed",
      description: message,
      progress: undefined,
    });
    toast.error("Upload failed", {
      id,
      description: message,
      action: onRetry ? { label: "Retry", onClick: onRetry } : undefined,
    });
  },

  exportSuccess(format: "csv" | "json", batchId: string) {
    const id = `export-${batchId}-${format}`;
    trackActivity({
      id,
      kind: "export",
      status: "success",
      title: `${format.toUpperCase()} exported`,
      description: batchId.slice(0, 8),
      href: ROUTES.batchDetail(batchId),
    });
    toast.success(`${format.toUpperCase()} export ready`, {
      description: `Batch ${batchId.slice(0, 8)}`,
    });
  },

  action(message: string, action: NotifyAction) {
    toast(message, { action: { label: action.label, onClick: action.onClick } });
  },
};

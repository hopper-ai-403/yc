"use client";

import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  FileDown,
  Loader2,
  Upload,
  X,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";

import { ProgressBar, StatusBadge } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { JOB_PROGRESS_REFETCH_MS, ROUTES } from "@/lib/constants";
import { formatRelativeTime } from "@/lib/format";
import { listJobs } from "@/services/batch";
import {
  useActivityStore,
  type ActivityItem,
  type ActivityKind,
} from "@/stores/activity-store";
import { useUiStore } from "@/stores/ui-store";
import { cn } from "@/lib/utils";

const KIND_ICON: Record<ActivityKind, typeof Activity> = {
  upload: Upload,
  job: Loader2,
  prediction: CheckCircle2,
  export: FileDown,
  error: AlertTriangle,
  system: Activity,
};

function mergeJobActivities(items: ActivityItem[]): ActivityItem[] {
  return [...items].sort((a, b) => b.updatedAt - a.updatedAt);
}

export function ActivityDrawer() {
  const open = useUiStore((s) => s.activityOpen);
  const setOpen = useUiStore((s) => s.setActivityOpen);
  const items = useActivityStore((s) => s.items);
  const push = useActivityStore((s) => s.push);
  const update = useActivityStore((s) => s.update);
  const remove = useActivityStore((s) => s.remove);
  const clear = useActivityStore((s) => s.clear);

  const jobsQuery = useQuery({
    queryKey: ["activity", "jobs"],
    queryFn: () => listJobs({ limit: 20 }),
    enabled: open,
    refetchInterval: (query) => {
      const active = query.state.data?.items.some(
        (job) =>
          job.status === "RUNNING" ||
          job.status === "QUEUED" ||
          job.status === "PENDING",
      );
      return active ? JOB_PROGRESS_REFETCH_MS : false;
    },
  });

  useEffect(() => {
    const jobs = jobsQuery.data?.items ?? [];
    for (const job of jobs) {
      const id = `job-${job.id}`;
      const status =
        job.status === "COMPLETED"
          ? "success"
          : job.status === "FAILED"
            ? "failed"
            : job.status === "QUEUED" || job.status === "PENDING"
              ? "queued"
              : job.status === "RUNNING"
                ? "running"
                : "info";
      const existing = useActivityStore.getState().items.find((item) => item.id === id);
      const payload = {
        id,
        kind: "job" as const,
        status: status as ActivityItem["status"],
        title: `Job ${job.status.toLowerCase()}`,
        description: `Batch ${job.batch_id.slice(0, 8)} · ${job.processed_files}/${job.total_files}`,
        href: ROUTES.batchDetail(job.batch_id),
        progress: job.progress,
        dismissible: status === "success" || status === "failed",
      };
      if (existing) update(id, payload);
      else if (status === "running" || status === "queued" || status === "failed") {
        push(payload);
      }
    }
  }, [jobsQuery.data, push, update]);

  const feed = useMemo(() => mergeJobActivities(items), [items]);
  const runningCount = feed.filter((item) => item.status === "running").length;

  return (
    <AnimatePresence>
      {open ? (
        <>
          <motion.button
            type="button"
            aria-label="Close activity panel"
            className="fixed inset-0 z-40 bg-background/50 backdrop-blur-[1px]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setOpen(false)}
          />
          <motion.aside
            initial={{ x: 24, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 24, opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col border-l border-border bg-card shadow-xl"
            role="dialog"
            aria-modal="true"
            aria-label="Activity feed"
          >
            <div className="flex h-14 items-center justify-between border-b border-border px-4">
              <div>
                <p className="text-sm font-semibold">Activity</p>
                <p className="text-[11px] text-muted-foreground">
                  {runningCount > 0
                    ? `${runningCount} running`
                    : "Newest first · auto-refresh while jobs run"}
                </p>
              </div>
              <div className="flex items-center gap-1">
                <Button size="sm" variant="ghost" onClick={clear}>
                  Clear
                </Button>
                <Button
                  size="icon"
                  variant="ghost"
                  aria-label="Close activity"
                  onClick={() => setOpen(false)}
                >
                  <X />
                </Button>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-3">
              {feed.length === 0 ? (
                <div className="flex h-full flex-col items-center justify-center gap-2 px-6 text-center">
                  <Activity className="size-8 text-muted-foreground/40" />
                  <p className="text-sm font-medium">No activity yet</p>
                  <p className="text-xs text-muted-foreground">
                    Uploads, running jobs, exports, and errors will appear here.
                  </p>
                </div>
              ) : (
                <ul className="space-y-2">
                  {feed.map((item) => {
                    const Icon = KIND_ICON[item.kind];
                    return (
                      <li
                        key={item.id}
                        className="rounded-lg border border-border bg-background/60 p-3"
                      >
                        <div className="flex items-start gap-2.5">
                          <div
                            className={cn(
                              "mt-0.5 rounded-md border border-border p-1.5",
                              item.status === "failed" && "border-destructive/30",
                            )}
                          >
                            <Icon
                              className={cn(
                                "size-3.5 text-muted-foreground",
                                item.status === "running" && "animate-spin text-info",
                                item.status === "success" && "text-success",
                                item.status === "failed" && "text-destructive",
                              )}
                            />
                          </div>
                          <div className="min-w-0 flex-1 space-y-1">
                            <div className="flex items-center gap-2">
                              <p className="truncate text-sm font-medium">{item.title}</p>
                              <StatusBadge
                                status={
                                  item.status === "success"
                                    ? "COMPLETED"
                                    : item.status === "failed"
                                      ? "FAILED"
                                      : item.status === "queued"
                                        ? "QUEUED"
                                        : item.status === "running"
                                          ? "RUNNING"
                                          : "PENDING"
                                }
                              />
                            </div>
                            {item.description ? (
                              <p className="truncate text-xs text-muted-foreground">
                                {item.description}
                              </p>
                            ) : null}
                            {typeof item.progress === "number" ? (
                              <ProgressBar value={item.progress} />
                            ) : null}
                            <div className="flex items-center justify-between pt-1">
                              <span className="text-[10px] text-muted-foreground">
                                {formatRelativeTime(new Date(item.updatedAt).toISOString())}
                              </span>
                              <div className="flex items-center gap-1">
                                {item.href ? (
                                  <Link
                                    href={item.href}
                                    onClick={() => setOpen(false)}
                                    className="text-[11px] font-medium text-foreground underline-offset-2 hover:underline"
                                  >
                                    Open
                                  </Link>
                                ) : null}
                                {item.dismissible !== false ? (
                                  <button
                                    type="button"
                                    aria-label="Dismiss"
                                    className="text-[11px] text-muted-foreground hover:text-foreground"
                                    onClick={() => remove(item.id)}
                                  >
                                    Dismiss
                                  </button>
                                ) : null}
                              </div>
                            </div>
                          </div>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
            <Separator />
            <div className="p-3 text-[10px] text-muted-foreground">
              Shortcut <span className="font-mono">A</span> opens activity ·{" "}
              <span className="font-mono">Esc</span> closes
            </div>
          </motion.aside>
        </>
      ) : null}
    </AnimatePresence>
  );
}

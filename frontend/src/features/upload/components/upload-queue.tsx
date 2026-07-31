"use client";

import { FileAudio, FileArchive, Loader2, CheckCircle2, X, AlertTriangle } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatBytes } from "@/lib/format";
import type { QueuedFile, UploadPhase } from "@/features/upload/hooks/use-upload";

function fileStatus(item: QueuedFile, phase: UploadPhase) {
  if (item.rejected) {
    return {
      label: "Rejected",
      icon: <AlertTriangle className="size-3.5 text-warning" />,
      detail: item.reason,
    };
  }
  if (phase === "success") {
    return {
      label: "Uploaded",
      icon: <CheckCircle2 className="size-3.5 text-success" />,
      detail: null,
    };
  }
  if (phase === "uploading") {
    return {
      label: "Uploading",
      icon: <Loader2 className="size-3.5 animate-spin text-info" />,
      detail: null,
    };
  }
  return { label: "Queued", icon: null, detail: null };
}

interface UploadQueueProps {
  queue: QueuedFile[];
  phase: UploadPhase;
  onRemove: (id: string) => void;
}

export function UploadQueue({ queue, phase, onRemove }: UploadQueueProps) {
  if (queue.length === 0) return null;

  return (
    <ul className="divide-y divide-border/60 rounded-xl border border-border bg-card" aria-label="Upload queue">
      <AnimatePresence initial={false}>
        {queue.map((item) => {
          const status = fileStatus(item, phase);
          const Icon = item.kind === "archive" ? FileArchive : FileAudio;
          return (
            <motion.li
              key={item.id}
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.15 }}
              className="flex items-center gap-3 overflow-hidden px-4 py-2.5"
            >
              <Icon className="size-4 shrink-0 text-muted-foreground" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm text-foreground">{item.name}</p>
                {status.detail ? (
                  <p className="text-xs text-warning">{status.detail}</p>
                ) : null}
              </div>
              <span className="shrink-0 font-mono text-xs tabular-nums text-muted-foreground">
                {formatBytes(item.size)}
              </span>
              <Badge
                variant={
                  item.rejected
                    ? "warning"
                    : phase === "success"
                      ? "success"
                      : phase === "uploading"
                        ? "info"
                        : "muted"
                }
              >
                {status.icon}
                {status.label}
              </Badge>
              {phase === "idle" ? (
                <Button
                  size="icon"
                  variant="ghost"
                  onClick={() => onRemove(item.id)}
                  aria-label={`Remove ${item.name}`}
                  className="size-7"
                >
                  <X className="size-3.5" />
                </Button>
              ) : (
                <span className="size-7" />
              )}
            </motion.li>
          );
        })}
      </AnimatePresence>
    </ul>
  );
}

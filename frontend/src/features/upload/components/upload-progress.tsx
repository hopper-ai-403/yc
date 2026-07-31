"use client";

import { motion } from "framer-motion";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { formatBytes, formatDurationMs } from "@/lib/format";
import type { UploadProgress } from "@/features/upload/hooks/use-upload";

interface UploadProgressPanelProps {
  progress: UploadProgress;
  onCancel: () => void;
}

export function UploadProgressPanel({
  progress,
  onCancel,
}: UploadProgressPanelProps) {
  const speed = progress.bytesPerSecond;
  const etaMs =
    progress.etaSeconds !== null ? progress.etaSeconds * 1000 : null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
    >
      <Card>
        <CardContent className="space-y-3 p-4">
          <div className="flex items-center justify-between gap-4">
            <p className="text-sm font-medium text-foreground">
              Uploading batch
            </p>
            <Button size="sm" variant="outline" onClick={onCancel}>
              Cancel
            </Button>
          </div>

          <div
            className="relative h-2 w-full overflow-hidden rounded-full bg-muted"
            role="progressbar"
            aria-valuenow={progress.percent}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Upload progress"
          >
            <motion.div
              className="h-full rounded-full bg-primary"
              initial={{ width: 0 }}
              animate={{ width: `${progress.percent}%` }}
              transition={{ duration: 0.25, ease: "easeOut" }}
            />
          </div>

          <dl className="grid grid-cols-2 gap-x-6 gap-y-1.5 text-xs sm:grid-cols-4">
            <div className="flex justify-between gap-2 sm:block">
              <dt className="text-muted-foreground">Progress</dt>
              <dd className="font-mono tabular-nums text-foreground">
                {progress.percent}%
              </dd>
            </div>
            <div className="flex justify-between gap-2 sm:block">
              <dt className="text-muted-foreground">Uploaded</dt>
              <dd className="font-mono tabular-nums text-foreground">
                {formatBytes(progress.loaded)} / {formatBytes(progress.total)}
              </dd>
            </div>
            <div className="flex justify-between gap-2 sm:block">
              <dt className="text-muted-foreground">Speed</dt>
              <dd className="font-mono tabular-nums text-foreground">
                {speed > 0 ? `${formatBytes(speed)}/s` : "—"}
              </dd>
            </div>
            <div className="flex justify-between gap-2 sm:block">
              <dt className="text-muted-foreground">Remaining</dt>
              <dd className="font-mono tabular-nums text-foreground">
                {progress.percent >= 100 ? "processing…" : formatDurationMs(etaMs)}
              </dd>
            </div>
          </dl>
        </CardContent>
      </Card>
    </motion.div>
  );
}

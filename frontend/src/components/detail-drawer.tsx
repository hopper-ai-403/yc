"use client";

import { X } from "lucide-react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";

import { CopyButton, JsonViewer, ProgressBar, StatusBadge } from "@/components/common";
import { Button } from "@/components/ui/button";
import { ROUTES } from "@/lib/constants";
import {
  formatConfidence,
  formatDateTime,
  formatDurationMs,
} from "@/lib/format";
import { getBatchMetrics, getBatchStatus } from "@/services/batch";
import { getAudioAsset, getAudioMetadata } from "@/services/audio";
import { getAudioPrediction } from "@/services/prediction";
import { useUiStore } from "@/stores/ui-store";

export function DetailDrawer() {
  const drawer = useUiStore((s) => s.drawer);
  const closeDrawer = useUiStore((s) => s.closeDrawer);

  return (
    <AnimatePresence>
      {drawer ? (
        <>
          <motion.button
            type="button"
            aria-label="Close detail drawer"
            className="fixed inset-0 z-40 bg-background/50"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={closeDrawer}
          />
          <motion.aside
            initial={{ x: 28, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 28, opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="fixed inset-y-0 right-0 z-50 flex w-full max-w-lg flex-col border-l border-border bg-card shadow-xl"
            role="dialog"
            aria-modal="true"
            aria-label={drawer.title ?? "Detail preview"}
          >
            <div className="flex h-14 items-center justify-between border-b border-border px-4">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold">
                  {drawer.title ?? drawer.kind}
                </p>
                <p className="truncate font-mono text-[11px] text-muted-foreground">
                  {drawer.id}
                </p>
              </div>
              <Button size="icon" variant="ghost" aria-label="Close" onClick={closeDrawer}>
                <X />
              </Button>
            </div>
            <div className="flex-1 overflow-y-auto p-4">
              {drawer.kind === "prediction" ? (
                <PredictionPreview audioId={drawer.id} />
              ) : null}
              {drawer.kind === "metadata" ? (
                <MetadataPreview audioId={drawer.id} />
              ) : null}
              {drawer.kind === "batch" ? <BatchPreview batchId={drawer.id} /> : null}
              {drawer.kind === "artifact" ? (
                <ArtifactPreview data={drawer.data ?? {}} />
              ) : null}
            </div>
          </motion.aside>
        </>
      ) : null}
    </AnimatePresence>
  );
}

function PredictionPreview({ audioId }: { audioId: string }) {
  const query = useQuery({
    queryKey: ["drawer", "prediction", audioId],
    queryFn: () => getAudioPrediction(audioId),
    staleTime: 60_000,
  });

  if (query.isLoading) return <p className="text-xs text-muted-foreground">Loading…</p>;
  if (query.isError || !query.data) {
    return <p className="text-xs text-destructive">Prediction unavailable.</p>;
  }

  const prediction = query.data.prediction;
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-foreground">Confidence</p>
        <span className="font-mono text-sm">{formatConfidence(prediction.confidence)}</span>
      </div>
      <JsonViewer data={prediction} defaultOpenDepth={2} className="max-h-[60vh]" />
      <div className="flex gap-2">
        <CopyButton value={JSON.stringify(prediction, null, 2)} label="Copy JSON" />
        <Link href={ROUTES.audioDetail(audioId)} onClick={() => useUiStore.getState().closeDrawer()}>
          <Button size="sm" variant="outline">
            Open explorer
          </Button>
        </Link>
      </div>
    </div>
  );
}

function MetadataPreview({ audioId }: { audioId: string }) {
  const assetQuery = useQuery({
    queryKey: ["drawer", "asset", audioId],
    queryFn: () => getAudioAsset(audioId),
  });
  const metaQuery = useQuery({
    queryKey: ["drawer", "metadata", audioId],
    queryFn: () => getAudioMetadata(audioId),
  });

  if (assetQuery.isLoading || metaQuery.isLoading) {
    return <p className="text-xs text-muted-foreground">Loading…</p>;
  }

  return (
    <div className="space-y-3">
      {assetQuery.data ? (
        <dl className="space-y-2 text-xs">
          <div className="flex justify-between gap-4">
            <dt className="text-muted-foreground">Filename</dt>
            <dd className="truncate font-mono">{assetQuery.data.filename}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-muted-foreground">Status</dt>
            <dd>
              <StatusBadge status={assetQuery.data.processing_status} />
            </dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-muted-foreground">Uploaded</dt>
            <dd>{formatDateTime(assetQuery.data.created_at)}</dd>
          </div>
        </dl>
      ) : null}
      {metaQuery.data?.metadata ? (
        <JsonViewer data={metaQuery.data.metadata} defaultOpenDepth={1} className="max-h-[50vh]" />
      ) : (
        <p className="text-xs text-muted-foreground">No metadata yet.</p>
      )}
      <Link href={ROUTES.audioDetail(audioId)} onClick={() => useUiStore.getState().closeDrawer()}>
        <Button size="sm" variant="outline">
          Open explorer
        </Button>
      </Link>
    </div>
  );
}

function BatchPreview({ batchId }: { batchId: string }) {
  const statusQuery = useQuery({
    queryKey: ["drawer", "batch-status", batchId],
    queryFn: () => getBatchStatus(batchId),
  });
  const metricsQuery = useQuery({
    queryKey: ["drawer", "batch-metrics", batchId],
    queryFn: () => getBatchMetrics(batchId),
    retry: false,
  });

  if (statusQuery.isLoading) {
    return <p className="text-xs text-muted-foreground">Loading…</p>;
  }

  const status = statusQuery.data;
  if (!status) {
    return <p className="text-xs text-destructive">Batch unavailable.</p>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <StatusBadge status={status.status} />
        <CopyButton value={batchId} label="Copy ID" />
      </div>
      <ProgressBar value={status.progress} failed={status.failed_files} />
      <dl className="grid grid-cols-2 gap-3 text-xs">
        <div>
          <dt className="text-muted-foreground">Files</dt>
          <dd className="font-mono">
            {status.processed_files}/{status.total_files}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Failed</dt>
          <dd className="font-mono">{status.failed_files}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Avg confidence</dt>
          <dd className="font-mono">
            {formatConfidence(metricsQuery.data?.average_confidence)}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Duration</dt>
          <dd className="font-mono">
            {formatDurationMs(metricsQuery.data?.batch_duration_ms)}
          </dd>
        </div>
      </dl>
      <div className="flex flex-wrap gap-2">
        <Link href={ROUTES.batchDetail(batchId)} onClick={() => useUiStore.getState().closeDrawer()}>
          <Button size="sm">Open batch</Button>
        </Link>
        <Link
          href={`${ROUTES.benchmark}?batch=${batchId}`}
          onClick={() => useUiStore.getState().closeDrawer()}
        >
          <Button size="sm" variant="outline">
            Benchmark
          </Button>
        </Link>
      </div>
    </div>
  );
}

function ArtifactPreview({ data }: { data: Record<string, unknown> }) {
  return (
    <div className="space-y-3">
      <JsonViewer data={data} defaultOpenDepth={2} />
      {"url" in data && typeof data.url === "string" ? (
        <a href={data.url} target="_blank" rel="noreferrer">
          <Button size="sm" variant="outline">
            Open artifact
          </Button>
        </a>
      ) : null}
    </div>
  );
}

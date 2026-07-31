"use client";

import { motion } from "framer-motion";

import { Progress } from "@/components/ui/progress";
import { formatConfidence, formatDurationMs } from "@/lib/format";

import { useAudioAsset, useAudioPrediction } from "../api";
import { FieldRow, SectionBody, SectionCard } from "./section";
import { PIPELINE_STAGES, stageDurationMs, totalDurationMs } from "../lib/timing";
import { formatEnumLabel } from "@/lib/format";

export function TimingPanel({ audioId }: { audioId: string }) {
  const asset = useAudioAsset(audioId);

  return (
    <SectionCard
      title="Pipeline Metrics"
      description="Per-stage profiling durations"
    >
      <SectionBody query={asset} pendingLabel="Audio asset">
        {(data) => {
          const timing = data.timing_json;
          const total = totalDurationMs(timing);
          const rows = PIPELINE_STAGES.map((stage) => ({
            stage,
            ms: stageDurationMs(timing, stage),
          }));
          const max = Math.max(...rows.map((row) => row.ms ?? 0), 1);

          if (!timing || total === null) {
            return (
              <p className="rounded-md border border-dashed border-border px-3 py-4 text-xs text-muted-foreground">
                Profiling data was not recorded for this asset.
              </p>
            );
          }

          return (
            <div className="space-y-3">
              {rows.map((row, index) =>
                row.ms === null ? null : (
                  <div key={row.stage} className="space-y-1">
                    <div className="flex items-baseline justify-between text-xs">
                      <span className="text-muted-foreground">
                        {formatEnumLabel(row.stage)}
                      </span>
                      <span className="font-mono tabular-nums text-foreground">
                        {formatDurationMs(row.ms)}
                      </span>
                    </div>
                    <motion.div
                      initial={{ scaleX: 0 }}
                      animate={{ scaleX: 1 }}
                      transition={{ delay: index * 0.05, duration: 0.25 }}
                      className="origin-left"
                    >
                      <Progress
                        value={(row.ms / max) * 100}
                        aria-label={`${row.stage} duration share`}
                      />
                    </motion.div>
                  </div>
                ),
              )}
              <div className="border-t border-border pt-2">
                <FieldRow
                  label="Total pipeline"
                  value={formatDurationMs(total)}
                  mono
                />
              </div>
            </div>
          );
        }}
      </SectionBody>
    </SectionCard>
  );
}

export function ConfidencePanel({ audioId }: { audioId: string }) {
  const query = useAudioPrediction(audioId);

  return (
    <SectionCard title="Confidence" description="Final prediction confidence">
      <SectionBody query={query} pendingLabel="Prediction" skeletonRows={2}>
        {(data) => (
          <div className="space-y-2">
            <p className="font-mono text-3xl font-semibold tabular-nums text-foreground">
              {formatConfidence(data.prediction.confidence)}
            </p>
            <Progress
              value={data.prediction.confidence * 100}
              aria-label="Prediction confidence"
            />
          </div>
        )}
      </SectionBody>
    </SectionCard>
  );
}

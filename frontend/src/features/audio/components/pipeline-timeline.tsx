"use client";

import { AnimatePresence, motion } from "framer-motion";
import {
  CheckCircle2,
  ChevronRight,
  Circle,
  Loader2,
  XCircle,
} from "lucide-react";
import { useState } from "react";

import { formatDurationMs, formatDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import type {
  AudioAcousticRead,
  AudioAssetRead,
  AudioSpeechRead,
  AudioTechnicalRead,
  PredictionRead,
} from "@/types/domain";

import { stageDurationMs, type PipelineStage } from "../lib/timing";
import { SectionCard } from "./section";

type StageStatus = "completed" | "active" | "failed" | "pending";

interface StageView {
  id: PipelineStage;
  label: string;
  status: StageStatus;
  timestamp: string | null;
  durationMs: number | null;
  details: Array<{ label: string; value: string }>;
}

const STATUS_ICON: Record<StageStatus, typeof Circle> = {
  completed: CheckCircle2,
  active: Loader2,
  failed: XCircle,
  pending: Circle,
};

const STATUS_COLOR: Record<StageStatus, string> = {
  completed: "text-success",
  active: "text-info",
  failed: "text-destructive",
  pending: "text-muted-foreground/50",
};

function deriveStatus(
  completed: boolean,
  prerequisiteDone: boolean,
  processing: boolean,
  failed: boolean,
): StageStatus {
  if (completed) return "completed";
  if (failed && prerequisiteDone) return "failed";
  if (prerequisiteDone && processing) return "active";
  return "pending";
}

function buildStages(
  asset: AudioAssetRead,
  technical: AudioTechnicalRead | undefined,
  acoustic: AudioAcousticRead | undefined,
  speech: AudioSpeechRead | undefined,
  prediction: PredictionRead | undefined,
): StageView[] {
  const timing = asset.timing_json;
  const processing = asset.processing_status === "PROCESSING";
  const failed = asset.processing_status === "FAILED";
  const duration = (stage: PipelineStage) => stageDurationMs(timing, stage);

  const preprocessed = asset.is_preprocessed;
  const analyzed = asset.analysis_completed;
  const technicalDone = technical?.technical_completed === true;
  const acousticDone = acoustic?.acoustic_completed === true;
  const speechDone = speech?.speech_completed === true;
  const predictionDone = prediction !== undefined;

  return [
    {
      id: "upload",
      label: "Upload",
      status: "completed",
      timestamp: asset.created_at,
      durationMs: duration("upload"),
      details: [
        { label: "Storage key", value: asset.storage_key },
        { label: "Size", value: `${asset.size_bytes} bytes` },
      ],
    },
    {
      id: "preprocessing",
      label: "Preprocessing",
      status: deriveStatus(preprocessed, true, processing, failed),
      timestamp: asset.preprocessed_at,
      durationMs: duration("preprocessing"),
      details: [
        {
          label: "Normalized key",
          value: asset.normalized_storage_key ?? "not created",
        },
      ],
    },
    {
      id: "analysis",
      label: "Analysis",
      status: deriveStatus(analyzed, preprocessed, processing, failed),
      timestamp: asset.analysis_completed_at,
      durationMs: duration("analysis"),
      details: [
        { label: "Version", value: asset.analysis_version ?? "—" },
        { label: "Artifact key", value: asset.analysis_storage_key ?? "—" },
      ],
    },
    {
      id: "technical",
      label: "Technical",
      status: deriveStatus(technicalDone, analyzed, processing, failed),
      timestamp: asset.technical_completed_at,
      durationMs: duration("technical"),
      details: [{ label: "Version", value: technical?.technical_version ?? "—" }],
    },
    {
      id: "acoustic",
      label: "Acoustic",
      status: deriveStatus(acousticDone, analyzed, processing, failed),
      timestamp: asset.acoustic_completed_at,
      durationMs: duration("acoustic"),
      details: [{ label: "Version", value: acoustic?.acoustic_version ?? "—" }],
    },
    {
      id: "speech",
      label: "Speech",
      status: deriveStatus(speechDone, analyzed, processing, failed),
      timestamp: asset.speech_completed_at,
      durationMs: duration("speech"),
      details: [{ label: "Version", value: speech?.speech_version ?? "—" }],
    },
    {
      id: "prediction",
      label: "Prediction",
      status: deriveStatus(
        predictionDone,
        technicalDone && acousticDone && speechDone,
        processing,
        failed,
      ),
      timestamp: null,
      durationMs: duration("prediction"),
      details: [
        { label: "Version", value: prediction?.prediction_version ?? "—" },
      ],
    },
  ];
}

export function PipelineTimeline({
  asset,
  technical,
  acoustic,
  speech,
  prediction,
}: {
  asset: AudioAssetRead;
  technical?: AudioTechnicalRead;
  acoustic?: AudioAcousticRead;
  speech?: AudioSpeechRead;
  prediction?: PredictionRead;
}) {
  const [expanded, setExpanded] = useState<PipelineStage | null>(null);
  const stages = buildStages(asset, technical, acoustic, speech, prediction);

  return (
    <SectionCard
      title="Pipeline Timeline"
      description="Stage execution and profiling data"
    >
      <ol className="space-y-0">
        {stages.map((stage, index) => {
          const Icon = STATUS_ICON[stage.status];
          const last = index === stages.length - 1;
          const open = expanded === stage.id;
          return (
            <motion.li
              key={stage.id}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.04, duration: 0.2 }}
              className="relative flex gap-3 pb-4 last:pb-0"
            >
              {!last ? (
                <span
                  aria-hidden
                  className="absolute left-[7px] top-5 h-full w-px bg-border"
                />
              ) : null}
              <Icon
                className={cn(
                  "mt-1 size-4 shrink-0",
                  STATUS_COLOR[stage.status],
                  stage.status === "active" && "animate-spin",
                )}
              />
              <div className="min-w-0 flex-1">
                <button
                  type="button"
                  onClick={() => setExpanded(open ? null : stage.id)}
                  aria-expanded={open}
                  className="flex w-full items-baseline justify-between gap-2 rounded text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <span className="flex items-center gap-1.5">
                    <ChevronRight
                      className={cn(
                        "size-3 text-muted-foreground transition-transform",
                        open && "rotate-90",
                      )}
                    />
                    <span
                      className={cn(
                        "text-sm",
                        stage.status === "pending"
                          ? "text-muted-foreground/60"
                          : "text-foreground",
                      )}
                    >
                      {stage.label}
                    </span>
                  </span>
                  <span className="flex shrink-0 items-baseline gap-2 font-mono text-[10px] text-muted-foreground">
                    <span className="tabular-nums">
                      {formatDurationMs(stage.durationMs)}
                    </span>
                    <span>{formatDateTime(stage.timestamp)}</span>
                  </span>
                </button>
                <AnimatePresence initial={false}>
                  {open ? (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.15 }}
                      className="overflow-hidden"
                    >
                      <dl className="ml-4 mt-1 space-y-1 border-l border-border pl-3 pb-1">
                        {stage.details.map((detail) => (
                          <div
                            key={detail.label}
                            className="flex items-baseline justify-between gap-4"
                          >
                            <dt className="text-[10px] uppercase tracking-wide text-muted-foreground">
                              {detail.label}
                            </dt>
                            <dd className="truncate font-mono text-[10px] text-foreground">
                              {detail.value}
                            </dd>
                          </div>
                        ))}
                      </dl>
                    </motion.div>
                  ) : null}
                </AnimatePresence>
              </div>
            </motion.li>
          );
        })}
      </ol>
    </SectionCard>
  );
}

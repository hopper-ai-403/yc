"use client";

import { Download } from "lucide-react";

import { CopyButton } from "@/components/common/copy-button";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { downloadJson } from "@/lib/download";
import { formatConfidence, formatEnumLabel } from "@/lib/format";

import { useAudioPrediction } from "../api";
import { SectionBody, SectionCard } from "./section";

const ENUM_FIELDS = [
  { key: "emotional_tone", label: "Emotional tone" },
  { key: "emotional_intensity", label: "Emotional intensity" },
  { key: "background_noise_type", label: "Noise type" },
  { key: "background_noise_severity", label: "Noise severity" },
  { key: "audio_quality", label: "Audio quality" },
] as const;

const BOOLEAN_FIELDS = [
  { key: "background_noise_present", label: "Noise present" },
  { key: "speaker_overlap_present", label: "Speaker overlap" },
  { key: "long_silence_present", label: "Long silence" },
] as const;

export function PredictionCard({ audioId }: { audioId: string }) {
  const query = useAudioPrediction(audioId);

  return (
    <SectionCard
      title="Final Prediction"
      description="Aggregated assessment output"
      className="border-primary/40"
      actions={
        query.data ? (
          <>
            <CopyButton
              size="icon"
              value={JSON.stringify(query.data.prediction, null, 2)}
            />
            <Button
              size="icon"
              variant="outline"
              aria-label="Download prediction JSON"
              onClick={() =>
                downloadJson(
                  query.data?.prediction,
                  `prediction-${audioId.slice(0, 8)}.json`,
                )
              }
            >
              <Download />
            </Button>
          </>
        ) : null
      }
    >
      <SectionBody query={query} pendingLabel="Final prediction">
        {(data) => {
          const prediction = data.prediction;
          return (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                {ENUM_FIELDS.map((field) => (
                  <div
                    key={field.key}
                    className="rounded-md border border-border bg-muted/30 px-3 py-2"
                  >
                    <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
                      {field.label}
                    </p>
                    <p className="mt-1 text-sm font-medium text-foreground">
                      {formatEnumLabel(String(prediction[field.key]))}
                    </p>
                  </div>
                ))}
                {BOOLEAN_FIELDS.map((field) => (
                  <div
                    key={field.key}
                    className="rounded-md border border-border bg-muted/30 px-3 py-2"
                  >
                    <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
                      {field.label}
                    </p>
                    <p className="mt-1 text-sm font-medium text-foreground">
                      {prediction[field.key] ? "Yes" : "No"}
                    </p>
                  </div>
                ))}
                <div className="rounded-md border border-border bg-muted/30 px-3 py-2">
                  <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
                    Confidence
                  </p>
                  <p className="mt-1 font-mono text-sm font-medium tabular-nums text-foreground">
                    {formatConfidence(prediction.confidence)}
                  </p>
                </div>
              </div>
              <div className="flex items-center justify-between text-[10px] text-muted-foreground">
                <span>
                  Prediction version{" "}
                  <span className="font-mono">
                    {data.prediction_version ?? "—"}
                  </span>
                </span>
                <Badge variant="muted">{ENUM_FIELDS.length + BOOLEAN_FIELDS.length + 1} fields</Badge>
              </div>
            </div>
          );
        }}
      </SectionBody>
    </SectionCard>
  );
}

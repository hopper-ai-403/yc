"use client";

import { Download, ExternalLink, Eye, FileAudio, FileJson } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { downloadJson } from "@/lib/download";
import { useUiStore } from "@/stores/ui-store";

import {
  useAudioAcoustic,
  useAudioAnalysis,
  useAudioAsset,
  useAudioDownload,
  useAudioPrediction,
  useAudioSpeech,
  useAudioTechnical,
} from "../api";
import { SectionBody, SectionCard } from "./section";
import type { InspectorTab } from "./json-inspector";

interface ArtifactRow {
  id: string;
  label: string;
  kind: "audio" | "json";
  available: boolean;
  detail: string;
  tab: InspectorTab | null;
  payload?: unknown;
}

export function ArtifactsPanel({
  audioId,
  onViewTab,
}: {
  audioId: string;
  onViewTab: (tab: InspectorTab) => void;
}) {
  const asset = useAudioAsset(audioId);
  const download = useAudioDownload(audioId);
  const analysis = useAudioAnalysis(audioId);
  const technical = useAudioTechnical(audioId);
  const acoustic = useAudioAcoustic(audioId);
  const speech = useAudioSpeech(audioId);
  const prediction = useAudioPrediction(audioId);
  const openDrawer = useUiStore((s) => s.openDrawer);

  const openDownloadUrl = () => {
    if (download.data) window.open(download.data.url, "_blank", "noopener");
  };

  return (
    <SectionCard
      title="Artifacts"
      description="Stored pipeline outputs"
    >
      <SectionBody query={asset} pendingLabel="Audio asset">
        {(data) => {
          const rows: ArtifactRow[] = [
            {
              id: "original",
              label: "Original audio",
              kind: "audio",
              available: true,
              detail: data.storage_key,
              tab: null,
            },
            {
              id: "normalized",
              label: "Normalized audio",
              kind: "audio",
              available: data.normalized_storage_key !== null,
              detail: data.normalized_storage_key ?? "not created",
              tab: null,
            },
            {
              id: "analysis",
              label: "Analysis",
              kind: "json",
              available: analysis.data?.analysis_completed === true,
              detail: data.analysis_storage_key ?? "—",
              tab: "analysis",
              payload: analysis.data?.analysis,
            },
            {
              id: "technical",
              label: "Technical",
              kind: "json",
              available: technical.data?.technical_completed === true,
              detail: technical.data?.technical_version ?? "—",
              tab: "technical",
              payload: technical.data,
            },
            {
              id: "acoustic",
              label: "Acoustic",
              kind: "json",
              available: acoustic.data?.acoustic_completed === true,
              detail: acoustic.data?.acoustic_version ?? "—",
              tab: "acoustic",
              payload: acoustic.data,
            },
            {
              id: "speech",
              label: "Speech",
              kind: "json",
              available: speech.data?.speech_completed === true,
              detail: speech.data?.speech_version ?? "—",
              tab: "speech",
              payload: speech.data,
            },
            {
              id: "prediction",
              label: "Prediction",
              kind: "json",
              available: prediction.data !== undefined,
              detail: prediction.data?.prediction_version ?? "—",
              tab: "prediction",
              payload: prediction.data?.prediction,
            },
          ];

          return (
            <ul className="divide-y divide-border">
              {rows.map((row) => {
                const Icon = row.kind === "audio" ? FileAudio : FileJson;
                return (
                  <li
                    key={row.id}
                    className="flex items-center gap-3 py-2 first:pt-0 last:pb-0"
                  >
                    <Icon className="size-4 shrink-0 text-muted-foreground" />
                    <div className="min-w-0 flex-1">
                      <p className="text-xs text-foreground">{row.label}</p>
                      <p className="truncate font-mono text-[10px] text-muted-foreground">
                        {row.detail}
                      </p>
                    </div>
                    <Badge variant={row.available ? "success" : "muted"}>
                      {row.available ? "Ready" : "Pending"}
                    </Badge>
                    <div className="flex shrink-0 items-center gap-1">
                      {row.kind === "audio" ? (
                        <Button
                          size="icon"
                          variant="ghost"
                          disabled={!row.available || !download.data}
                          aria-label={`Download ${row.label.toLowerCase()}`}
                          onClick={openDownloadUrl}
                        >
                          <Download />
                        </Button>
                      ) : (
                        <>
                          <Button
                            size="icon"
                            variant="ghost"
                            disabled={!row.available}
                            aria-label={`Preview ${row.label.toLowerCase()}`}
                            onClick={() =>
                              openDrawer({
                                kind: "artifact",
                                id: `${audioId}-${row.id}`,
                                title: row.label,
                                data:
                                  row.payload !== undefined &&
                                  typeof row.payload === "object" &&
                                  row.payload !== null &&
                                  !Array.isArray(row.payload)
                                    ? (row.payload as Record<string, unknown>)
                                    : { detail: row.detail, value: row.payload },
                              })
                            }
                          >
                            <Eye />
                          </Button>
                          <Button
                            size="icon"
                            variant="ghost"
                            disabled={!row.available || row.tab === null}
                            aria-label={`Open ${row.label.toLowerCase()} payload`}
                            onClick={() => row.tab && onViewTab(row.tab)}
                          >
                            <ExternalLink />
                          </Button>
                          <Button
                            size="icon"
                            variant="ghost"
                            disabled={!row.available}
                            aria-label={`Download ${row.label.toLowerCase()} JSON`}
                            onClick={() =>
                              downloadJson(
                                row.payload,
                                `${row.id}-${audioId.slice(0, 8)}.json`,
                              )
                            }
                          >
                            <Download />
                          </Button>
                        </>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          );
        }}
      </SectionBody>
    </SectionCard>
  );
}

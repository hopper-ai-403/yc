"use client";

import { Badge } from "@/components/ui/badge";
import {
  formatAudioDuration,
  formatBytes,
  formatDateTime,
} from "@/lib/format";

import { useAudioAsset, useAudioMetadata } from "../api";
import { FieldRow, SectionBody, SectionCard } from "./section";

function readProbeString(
  probe: Record<string, unknown>,
  keys: string[],
): string | null {
  for (const key of keys) {
    const value = probe[key];
    if (typeof value === "string" && value.length > 0) return value;
  }
  return null;
}

function readProbeBitrate(probe: Record<string, unknown>): string | null {
  const raw = probe.bitrate ?? probe.bit_rate;
  const value = typeof raw === "string" ? Number(raw) : raw;
  if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) {
    return null;
  }
  const kbps = value > 10_000 ? value / 1000 : value;
  return `${Math.round(kbps)} kbps`;
}

export function MetadataCard({ audioId }: { audioId: string }) {
  const asset = useAudioAsset(audioId);
  const metadata = useAudioMetadata(audioId);

  return (
    <SectionCard title="Metadata" description="Asset and probe information">
      <SectionBody query={asset} pendingLabel="Audio asset">
        {(data) => {
          const probe = metadata.data?.metadata ?? {};
          const codec =
            readProbeString(probe, ["codec", "codec_name", "audio_codec"]) ??
            data.format;
          const container =
            readProbeString(probe, ["container", "format_name"]) ??
            data.extension;
          const bitrate = readProbeBitrate(probe);
          return (
            <dl>
              <FieldRow label="Filename" value={data.filename} mono />
              <FieldRow
                label="Duration"
                value={formatAudioDuration(data.duration)}
                mono
              />
              <FieldRow
                label="Sample rate"
                value={
                  data.sample_rate ? `${data.sample_rate.toLocaleString()} Hz` : "—"
                }
                mono
              />
              <FieldRow
                label="Channels"
                value={data.channels ?? "—"}
                mono
              />
              <FieldRow label="Codec" value={codec || "—"} mono />
              <FieldRow label="Bitrate" value={bitrate ?? "—"} mono />
              <FieldRow label="Container" value={container || "—"} mono />
              <FieldRow label="Size" value={formatBytes(data.size_bytes)} mono />
              <FieldRow
                label="Uploaded"
                value={formatDateTime(data.created_at)}
                mono
              />
              <FieldRow
                label="Preprocessed"
                value={
                  <Badge variant={data.is_preprocessed ? "default" : "muted"}>
                    {data.is_preprocessed ? "Yes" : "No"}
                  </Badge>
                }
              />
              <FieldRow
                label="Analysis version"
                value={data.analysis_version ?? "—"}
                mono
              />
            </dl>
          );
        }}
      </SectionBody>
    </SectionCard>
  );
}

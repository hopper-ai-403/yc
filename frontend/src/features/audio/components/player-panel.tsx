"use client";

import { AudioPlayer } from "@/components/common/audio-player";
import { WaveformViewer } from "@/components/common/waveform-viewer";
import { ErrorState } from "@/components/common/error-state";
import { Skeleton } from "@/components/ui/skeleton";

import { useAudioDownload, useAudioSegments } from "../api";
import { SectionCard } from "./section";

export function PlayerPanel({ audioId }: { audioId: string }) {
  const download = useAudioDownload(audioId);
  const segments = useAudioSegments(audioId);

  return (
    <SectionCard
      title="Audio Player"
      description={
        download.data
          ? `Source: ${download.data.content_variant}`
          : "Normalized playback source"
      }
    >
      {download.isPending ? (
        <div className="space-y-3" aria-busy="true">
          <Skeleton className="h-11 w-full" />
          <Skeleton className="h-32 w-full" />
        </div>
      ) : download.isError ? (
        <ErrorState
          error={download.error}
          title="Audio source unavailable"
          onRetry={() => void download.refetch()}
        />
      ) : (
        <div className="space-y-3">
          <AudioPlayer src={download.data.url} />
          <WaveformViewer
            url={download.data.url}
            segments={segments.data?.speech_segments ?? []}
            silenceSegments={segments.data?.silence_segments ?? []}
            height={112}
            zoomable
          />
          {segments.data ? (
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-muted-foreground">
              <span>
                Speech {segments.data.speech_duration.toFixed(1)}s (
                {(segments.data.speech_ratio * 100).toFixed(0)}%)
              </span>
              <span>
                Largest silence {segments.data.largest_silence.toFixed(1)}s
              </span>
            </div>
          ) : null}
        </div>
      )}
    </SectionCard>
  );
}

"use client";

import { Pause, Play, ZoomIn, ZoomOut } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type WaveSurfer from "wavesurfer.js";

import { Button } from "@/components/ui/button";
import { LoadingBlock } from "@/components/common/loading-spinner";
import { cn } from "@/lib/utils";
import type { TimeSegment } from "@/types/domain";

interface WaveformViewerProps {
  url: string;
  /** Speech segments highlighted under the waveform. */
  segments?: TimeSegment[];
  /** Silence segments rendered on a secondary track. */
  silenceSegments?: TimeSegment[];
  height?: number;
  className?: string;
  onReady?: (duration: number) => void;
  /** Show zoom in/out controls. */
  zoomable?: boolean;
}

const MIN_PX_PER_SEC = 8;
const MAX_PX_PER_SEC = 512;

/** WaveSurfer-based waveform with optional speech-segment overlay. */
export function WaveformViewer({
  url,
  segments = [],
  silenceSegments = [],
  height = 96,
  className,
  onReady,
  zoomable = false,
}: WaveformViewerProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const wavesurferRef = useRef<WaveSurfer | null>(null);
  const [ready, setReady] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [duration, setDuration] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [pxPerSec, setPxPerSec] = useState(0);

  const zoom = (factor: number) => {
    const next = Math.min(
      MAX_PX_PER_SEC,
      Math.max(MIN_PX_PER_SEC, (pxPerSec || MIN_PX_PER_SEC) * factor),
    );
    wavesurferRef.current?.zoom(next);
    setPxPerSec(next);
  };

  useEffect(() => {
    let cancelled = false;

    async function init() {
      if (!containerRef.current) return;
      const { default: WaveSurferImpl } = await import("wavesurfer.js");
      if (cancelled || !containerRef.current) return;

      const styles = getComputedStyle(document.documentElement);
      const waveColor = styles.getPropertyValue("--muted-foreground").trim();
      const progressColor = styles.getPropertyValue("--foreground").trim();

      const ws = WaveSurferImpl.create({
        container: containerRef.current,
        height,
        waveColor: `hsl(${waveColor} / 0.4)`,
        progressColor: `hsl(${progressColor} / 0.9)`,
        cursorColor: `hsl(${progressColor})`,
        cursorWidth: 1,
        barWidth: 2,
        barGap: 1,
        barRadius: 1,
        normalize: true,
        url,
      });

      ws.on("ready", (dur) => {
        if (cancelled) return;
        setReady(true);
        setDuration(dur);
        if (containerRef.current && dur > 0) {
          setPxPerSec(containerRef.current.clientWidth / dur);
        }
        onReady?.(dur);
      });
      ws.on("play", () => setPlaying(true));
      ws.on("pause", () => setPlaying(false));
      ws.on("finish", () => setPlaying(false));
      ws.on("error", (err) => setError(err?.message ?? "Failed to load audio"));

      wavesurferRef.current = ws;
    }

    void init();
    return () => {
      cancelled = true;
      wavesurferRef.current?.destroy();
      wavesurferRef.current = null;
      setReady(false);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, height]);

  return (
    <div
      className={cn(
        "rounded-md border border-border bg-card p-3",
        className,
      )}
    >
      <div className="relative">
        {!ready && !error ? <LoadingBlock label="Loading waveform…" /> : null}
        {error ? (
          <div className="flex h-24 items-center justify-center text-xs text-destructive">
            {error}
          </div>
        ) : null}
        <div ref={containerRef} className={cn(!ready && "invisible h-0")} />
        {ready && duration > 0 && segments.length > 0 ? (
          <div
            aria-hidden
            className="pointer-events-none absolute inset-x-0 bottom-0 h-1.5"
          >
            {segments.map((segment, index) => {
              const left = (segment.start / duration) * 100;
              const width = Math.max(
                0.5,
                ((segment.end - segment.start) / duration) * 100,
              );
              return (
                <span
                  key={`${segment.start}-${index}`}
                  className="absolute bottom-0 h-full rounded-full bg-info/60"
                  style={{ left: `${left}%`, width: `${width}%` }}
                />
              );
            })}
          </div>
        ) : null}
        {ready && duration > 0 && silenceSegments.length > 0 ? (
          <div
            aria-hidden
            className="pointer-events-none absolute inset-x-0 bottom-2 h-1"
          >
            {silenceSegments.map((segment, index) => {
              const left = (segment.start / duration) * 100;
              const width = Math.max(
                0.5,
                ((segment.end - segment.start) / duration) * 100,
              );
              return (
                <span
                  key={`${segment.start}-${index}`}
                  className="absolute bottom-0 h-full rounded-full bg-warning/50"
                  style={{ left: `${left}%`, width: `${width}%` }}
                />
              );
            })}
          </div>
        ) : null}
      </div>
      <div className="mt-2 flex items-center gap-2">
        <Button
          size="sm"
          variant="outline"
          disabled={!ready}
          onClick={() => void wavesurferRef.current?.playPause()}
          aria-label={playing ? "Pause playback" : "Start playback"}
        >
          {playing ? <Pause /> : <Play />}
          {playing ? "Pause" : "Play"}
        </Button>
        {zoomable ? (
          <div className="flex items-center gap-1">
            <Button
              size="icon"
              variant="ghost"
              disabled={!ready || pxPerSec >= MAX_PX_PER_SEC}
              onClick={() => zoom(2)}
              aria-label="Zoom in"
            >
              <ZoomIn />
            </Button>
            <Button
              size="icon"
              variant="ghost"
              disabled={!ready || pxPerSec <= MIN_PX_PER_SEC}
              onClick={() => zoom(0.5)}
              aria-label="Zoom out"
            >
              <ZoomOut />
            </Button>
          </div>
        ) : null}
        {segments.length > 0 ? (
          <span className="text-[10px] text-muted-foreground">
            Blue bars mark speech{silenceSegments.length > 0 ? ", amber bars mark silence" : ""}
          </span>
        ) : null}
      </div>
    </div>
  );
}

"use client";

import { Pause, Play, Volume2, VolumeX } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { formatAudioDuration } from "@/lib/format";
import { cn } from "@/lib/utils";

interface AudioPlayerProps {
  src: string;
  className?: string;
}

/** Minimal transport controls over a plain <audio> element. */
export function AudioPlayer({ src, className }: AudioPlayerProps) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [playing, setPlaying] = useState(false);
  const [muted, setMuted] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState<number | null>(null);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    const onTime = () => setCurrentTime(audio.currentTime);
    const onMeta = () =>
      setDuration(Number.isFinite(audio.duration) ? audio.duration : null);
    const onEnd = () => setPlaying(false);
    audio.addEventListener("timeupdate", onTime);
    audio.addEventListener("loadedmetadata", onMeta);
    audio.addEventListener("ended", onEnd);
    return () => {
      audio.removeEventListener("timeupdate", onTime);
      audio.removeEventListener("loadedmetadata", onMeta);
      audio.removeEventListener("ended", onEnd);
    };
  }, [src]);

  const toggle = () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (playing) {
      audio.pause();
    } else {
      void audio.play();
    }
    setPlaying(!playing);
  };

  const seek = (value: number) => {
    const audio = audioRef.current;
    if (!audio || duration === null) return;
    audio.currentTime = value;
    setCurrentTime(value);
  };

  return (
    <div
      className={cn(
        "flex items-center gap-3 rounded-md border border-border bg-card px-3 py-2",
        className,
      )}
    >
      <audio ref={audioRef} src={src} preload="metadata" muted={muted} />
      <Button
        size="icon"
        variant="ghost"
        onClick={toggle}
        aria-label={playing ? "Pause" : "Play"}
      >
        {playing ? <Pause /> : <Play />}
      </Button>
      <span className="w-10 text-right font-mono text-xs tabular-nums text-muted-foreground">
        {formatAudioDuration(currentTime)}
      </span>
      <input
        type="range"
        min={0}
        max={duration ?? 0}
        step={0.1}
        value={currentTime}
        onChange={(event) => seek(Number(event.target.value))}
        aria-label="Seek"
        className="h-1 flex-1 cursor-pointer appearance-none rounded-full bg-muted accent-primary"
      />
      <span className="w-10 font-mono text-xs tabular-nums text-muted-foreground">
        {formatAudioDuration(duration)}
      </span>
      <Button
        size="icon"
        variant="ghost"
        onClick={() => setMuted((prev) => !prev)}
        aria-label={muted ? "Unmute" : "Mute"}
      >
        {muted ? <VolumeX /> : <Volume2 />}
      </Button>
    </div>
  );
}

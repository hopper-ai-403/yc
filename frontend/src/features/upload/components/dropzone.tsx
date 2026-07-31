"use client";

import { CloudUpload } from "lucide-react";
import { useCallback, useRef, useState, type DragEvent } from "react";

import { cn } from "@/lib/utils";
import {
  MAX_FILE_SIZE_BYTES,
  MAX_ZIP_SIZE_BYTES,
} from "@/features/upload/hooks/use-upload";
import { formatBytes } from "@/lib/format";

interface DropzoneProps {
  onFiles: (files: File[]) => void;
  disabled?: boolean;
}

export function Dropzone({ onFiles, disabled = false }: DropzoneProps) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const depthRef = useRef(0);

  const handleDrop = useCallback(
    (event: DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      depthRef.current = 0;
      setDragging(false);
      if (disabled) return;
      const files = [...event.dataTransfer.files];
      if (files.length > 0) onFiles(files);
    },
    [disabled, onFiles],
  );

  return (
    <div
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-label="Drop files to upload, or press Enter to browse"
      aria-disabled={disabled}
      onClick={() => !disabled && inputRef.current?.click()}
      onKeyDown={(event) => {
        if (disabled) return;
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          inputRef.current?.click();
        }
      }}
      onDragEnter={(event) => {
        event.preventDefault();
        depthRef.current += 1;
        if (!disabled) setDragging(true);
      }}
      onDragLeave={(event) => {
        event.preventDefault();
        depthRef.current -= 1;
        if (depthRef.current <= 0) setDragging(false);
      }}
      onDragOver={(event) => event.preventDefault()}
      onDrop={handleDrop}
      className={cn(
        "flex cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border border-dashed px-6 py-14 text-center transition-colors",
        "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
        dragging
          ? "border-foreground/40 bg-accent/40"
          : "border-border bg-muted/20 hover:bg-muted/40",
        disabled && "pointer-events-none opacity-50",
      )}
    >
      <div className="rounded-lg border border-border bg-muted/60 p-3">
        <CloudUpload className="size-5 text-muted-foreground" />
      </div>
      <div className="space-y-1">
        <p className="text-sm font-medium text-foreground">
          Drop a ZIP archive or audio files here
        </p>
        <p className="text-xs text-muted-foreground">
          or click to browse your filesystem
        </p>
      </div>
      <div className="flex flex-wrap items-center justify-center gap-1.5 text-[11px] text-muted-foreground">
        <span className="rounded-md border border-border px-1.5 py-0.5 font-mono">
          .wav .mp3 .ogg
        </span>
        <span className="rounded-md border border-border px-1.5 py-0.5 font-mono">
          .zip
        </span>
        <span className="px-1">·</span>
        <span>max {formatBytes(MAX_FILE_SIZE_BYTES)} per file</span>
        <span className="px-1">·</span>
        <span>max {formatBytes(MAX_ZIP_SIZE_BYTES)} per ZIP</span>
      </div>
      <input
        ref={inputRef}
        type="file"
        multiple
        accept=".wav,.mp3,.ogg,.zip"
        className="hidden"
        tabIndex={-1}
        aria-hidden="true"
        onChange={(event) => {
          const files = [...(event.target.files ?? [])];
          if (files.length > 0) onFiles(files);
          event.target.value = "";
        }}
      />
    </div>
  );
}

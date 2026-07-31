"use client";

import { useCallback, useMemo, useRef, useState } from "react";

import {
  ACCEPTED_ARCHIVE_EXTENSIONS,
  ACCEPTED_AUDIO_EXTENSIONS,
} from "@/lib/constants";
import { ApiError } from "@/services/client";
import { uploadFiles } from "@/services/upload";
import type { UploadResultData } from "@/types/domain";

export const MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024;
export const MAX_ZIP_SIZE_BYTES = 500 * 1024 * 1024;
export const MAX_FILES_PER_BATCH = 500;

const ACCEPTED_EXTENSIONS = [
  ...ACCEPTED_AUDIO_EXTENSIONS,
  ...ACCEPTED_ARCHIVE_EXTENSIONS,
];

export type UploadPhase = "idle" | "uploading" | "success" | "error";

export interface QueuedFile {
  id: string;
  file: File;
  name: string;
  size: number;
  kind: "archive" | "audio";
  rejected: boolean;
  reason?: string;
}

export interface UploadProgress {
  loaded: number;
  total: number;
  percent: number;
  bytesPerSecond: number;
  etaSeconds: number | null;
}

function fileExtension(name: string): string {
  const index = name.lastIndexOf(".");
  return index >= 0 ? name.slice(index).toLowerCase() : "";
}

export function toQueuedFile(file: File): QueuedFile {
  const extension = fileExtension(file.name);
  const kind = extension === ".zip" ? "archive" : "audio";
  let rejected = false;
  let reason: string | undefined;

  if (!ACCEPTED_EXTENSIONS.includes(extension as never)) {
    rejected = true;
    reason = `Unsupported format ${extension || "(none)"}`;
  } else if (kind === "archive" && file.size > MAX_ZIP_SIZE_BYTES) {
    rejected = true;
    reason = "Exceeds 500 MB ZIP limit";
  } else if (kind === "audio" && file.size > MAX_FILE_SIZE_BYTES) {
    rejected = true;
    reason = "Exceeds 100 MB file limit";
  }

  return {
    id: `${file.name}-${file.size}-${file.lastModified}`,
    file,
    name: file.name,
    size: file.size,
    kind,
    rejected,
    reason,
  };
}

export function useUpload() {
  const [queue, setQueue] = useState<QueuedFile[]>([]);
  const [phase, setPhase] = useState<UploadPhase>("idle");
  const [progress, setProgress] = useState<UploadProgress | null>(null);
  const [result, setResult] = useState<UploadResultData | null>(null);
  const [error, setError] = useState<ApiError | null>(null);

  const abortRef = useRef<AbortController | null>(null);
  const speedSamplesRef = useRef<{ at: number; loaded: number }[]>([]);

  const totalBytes = useMemo(
    () =>
      queue.filter((item) => !item.rejected).reduce((sum, item) => sum + item.size, 0),
    [queue],
  );

  const uploadable = useMemo(
    () => queue.filter((item) => !item.rejected),
    [queue],
  );

  const addFiles = useCallback((files: File[]) => {
    setQueue((current) => {
      const existing = new Set(current.map((item) => item.id));
      const additions = files
        .map(toQueuedFile)
        .filter((item) => !existing.has(item.id));
      return [...current, ...additions].slice(0, MAX_FILES_PER_BATCH);
    });
  }, []);

  const removeFile = useCallback((id: string) => {
    setQueue((current) => current.filter((item) => item.id !== id));
  }, []);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setQueue([]);
    setPhase("idle");
    setProgress(null);
    setResult(null);
    setError(null);
    speedSamplesRef.current = [];
  }, []);

  const start = useCallback(async () => {
    if (uploadable.length === 0 || phase === "uploading") return;

    const controller = new AbortController();
    abortRef.current = controller;
    speedSamplesRef.current = [];
    setPhase("uploading");
    setError(null);
    setResult(null);
    setProgress({
      loaded: 0,
      total: totalBytes,
      percent: 0,
      bytesPerSecond: 0,
      etaSeconds: null,
    });

    const onProgress = (percent: number) => {
      const loaded = (percent / 100) * totalBytes;
      const now = Date.now();
      const samples = speedSamplesRef.current;
      samples.push({ at: now, loaded });
      while (samples.length > 2 && now - samples[0].at > 5_000) samples.shift();

      let bytesPerSecond = 0;
      let etaSeconds: number | null = null;
      if (samples.length >= 2) {
        const first = samples[0];
        const elapsed = (now - first.at) / 1000;
        if (elapsed > 0.2) {
          bytesPerSecond = Math.max(0, (loaded - first.loaded) / elapsed);
          etaSeconds =
            bytesPerSecond > 0 ? (totalBytes - loaded) / bytesPerSecond : null;
        }
      }
      setProgress({ loaded, total: totalBytes, percent, bytesPerSecond, etaSeconds });
    };

    try {
      const response = await uploadFiles(
        uploadable.map((item) => item.file),
        { onProgress, signal: controller.signal },
      );
      setResult(response);
      setPhase("success");
    } catch (cause) {
      if (controller.signal.aborted) {
        setPhase("idle");
        setProgress(null);
        return;
      }
      setError(
        cause instanceof ApiError
          ? cause
          : new ApiError({ message: "Upload failed", code: "UPLOAD_ERROR", status: 0 }),
      );
      setPhase("error");
    } finally {
      abortRef.current = null;
    }
  }, [uploadable, phase, totalBytes]);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  return {
    queue,
    phase,
    progress,
    result,
    error,
    totalBytes,
    uploadableCount: uploadable.length,
    rejectedCount: queue.length - uploadable.length,
    addFiles,
    removeFile,
    start,
    cancel,
    reset,
  };
}

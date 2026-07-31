import { post } from "./client";

import type { UploadResultData } from "@/types/domain";

export interface UploadOptions {
  onProgress?: (percent: number) => void;
  signal?: AbortSignal;
}

/** Upload ZIP archives and/or audio files; creates batch + job. */
export async function uploadFiles(
  files: File[],
  options: UploadOptions = {},
): Promise<UploadResultData> {
  const form = new FormData();
  for (const file of files) {
    form.append("files", file, file.name);
  }
  return post<UploadResultData>("/uploads", form, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 300_000,
    signal: options.signal,
    onUploadProgress: (event) => {
      if (!options.onProgress || !event.total) return;
      options.onProgress(Math.round((event.loaded / event.total) * 100));
    },
  });
}

export const uploadApi = { uploadFiles };

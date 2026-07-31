"use client";

import { ArrowUpFromLine } from "lucide-react";

import { ErrorState } from "@/components/common";
import { PageContainer, PageHeader } from "@/components/layout";
import { Button } from "@/components/ui/button";
import { formatBytes } from "@/lib/format";

import { Dropzone } from "@/features/upload/components/dropzone";
import { UploadProgressPanel } from "@/features/upload/components/upload-progress";
import { UploadQueue } from "@/features/upload/components/upload-queue";
import { UploadSuccess } from "@/features/upload/components/upload-success";
import { useUpload } from "@/features/upload/hooks/use-upload";

export function UploadStudio() {
  const upload = useUpload();
  const busy = upload.phase === "uploading";

  return (
    <PageContainer className="max-w-3xl">
      <PageHeader
        title="Upload Studio"
        description="Create a batch from a ZIP archive or individual call recordings. Processing starts automatically once the upload lands."
      />

      {upload.phase === "success" && upload.result ? (
        <UploadSuccess result={upload.result} onReset={upload.reset} />
      ) : (
        <div className="space-y-4">
          <Dropzone onFiles={upload.addFiles} disabled={busy} />

          {upload.queue.length > 0 ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span className="tabular-nums">
                  {upload.uploadableCount}{" "}
                  {upload.uploadableCount === 1 ? "file" : "files"} ready
                  {upload.rejectedCount > 0
                    ? ` · ${upload.rejectedCount} rejected client-side`
                    : ""}
                </span>
                <span className="font-mono tabular-nums">
                  {formatBytes(upload.totalBytes)} total
                </span>
              </div>

              <UploadQueue
                queue={upload.queue}
                phase={upload.phase}
                onRemove={upload.removeFile}
              />

              {upload.phase === "uploading" && upload.progress ? (
                <UploadProgressPanel
                  progress={upload.progress}
                  onCancel={upload.cancel}
                />
              ) : (
                <div className="flex items-center justify-end gap-2">
                  <Button size="sm" variant="outline" onClick={upload.reset}>
                    Clear
                  </Button>
                  <Button
                    size="sm"
                    onClick={() => void upload.start()}
                    disabled={upload.uploadableCount === 0}
                  >
                    <ArrowUpFromLine />
                    Start upload
                  </Button>
                </div>
              )}
            </div>
          ) : null}

          {upload.phase === "error" ? (
            <ErrorState
              error={upload.error}
              title="Upload failed"
              onRetry={() => void upload.start()}
            />
          ) : null}
        </div>
      )}
    </PageContainer>
  );
}

"use client";

import { FileUp } from "lucide-react";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  parseGroundTruth,
} from "@/features/evaluation/lib/compare";
import type { BatchExportResultRow } from "@/types/domain";

interface GroundTruthUploaderProps {
  onLoaded: (rows: BatchExportResultRow[], source: string) => void;
  onError: (message: string) => void;
}

export function GroundTruthUploader({
  onLoaded,
  onError,
}: GroundTruthUploaderProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  async function handleFile(file: File) {
    try {
      const text = await file.text();
      const rows = parseGroundTruth(text);
      if (rows.length === 0) {
        onError("Ground-truth file contained no rows");
        return;
      }
      onLoaded(rows, file.name);
    } catch (error) {
      onError(error instanceof Error ? error.message : "Failed to parse file");
    }
  }

  return (
    <Card>
      <CardContent className="p-4">
        <div
          role="button"
          tabIndex={0}
          aria-label="Upload ground-truth JSON or CSV"
          onClick={() => inputRef.current?.click()}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              inputRef.current?.click();
            }
          }}
          onDragEnter={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={(event) => {
            event.preventDefault();
            setDragging(false);
          }}
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            event.preventDefault();
            setDragging(false);
            const file = event.dataTransfer.files[0];
            if (file) void handleFile(file);
          }}
          className={
            dragging
              ? "flex cursor-pointer flex-col items-center gap-2 rounded-xl border border-dashed border-foreground/40 bg-accent/40 px-4 py-8 text-center"
              : "flex cursor-pointer flex-col items-center gap-2 rounded-xl border border-dashed border-border bg-muted/20 px-4 py-8 text-center hover:bg-muted/40"
          }
        >
          <FileUp className="size-5 text-muted-foreground" />
          <p className="text-sm font-medium">Upload expected labels</p>
          <p className="max-w-md text-xs text-muted-foreground">
            Accepts assessment CSV (<span className="font-mono">filename,result_json</span>)
            or JSON array of <span className="font-mono">{"{filename, result}"}</span>.
          </p>
          <Button size="sm" variant="outline" type="button">
            Browse files
          </Button>
        </div>
        <input
          ref={inputRef}
          type="file"
          accept=".json,.csv,application/json,text/csv"
          className="hidden"
          aria-hidden="true"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) void handleFile(file);
            event.target.value = "";
          }}
        />
      </CardContent>
    </Card>
  );
}

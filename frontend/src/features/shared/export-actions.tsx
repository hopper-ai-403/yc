"use client";

import { FileJson, FileSpreadsheet } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { downloadBlob, downloadJson } from "@/lib/download";
import { downloadBatchCsv, getBatchExportJson } from "@/services/batch";
import { ApiError } from "@/services/client";

export function useExportActions() {
  const [pending, setPending] = useState<string | null>(null);

  async function exportCsv(batchId: string): Promise<void> {
    const key = `${batchId}:csv`;
    if (pending) return;
    setPending(key);
    try {
      const blob = await downloadBatchCsv(batchId);
      downloadBlob(blob, `results-${batchId}.csv`);
      toast.success("CSV export downloaded");
    } catch (error) {
      toast.error(
        error instanceof ApiError ? error.message : "CSV export failed",
      );
    } finally {
      setPending(null);
    }
  }

  async function exportJson(batchId: string): Promise<void> {
    const key = `${batchId}:json`;
    if (pending) return;
    setPending(key);
    try {
      const payload = await getBatchExportJson(batchId);
      downloadJson(payload, `results-${batchId}.json`);
      toast.success("JSON export downloaded");
    } catch (error) {
      toast.error(
        error instanceof ApiError ? error.message : "JSON export failed",
      );
    } finally {
      setPending(null);
    }
  }

  return { pending, exportCsv, exportJson };
}

interface ExportButtonsProps {
  batchId: string;
  pending: string | null;
  onCsv: (batchId: string) => void;
  onJson: (batchId: string) => void;
}

export function ExportButtons({
  batchId,
  pending,
  onCsv,
  onJson,
}: ExportButtonsProps) {
  const busy = pending !== null;
  return (
    <div className="flex items-center gap-1">
      <Button
        size="icon"
        variant="ghost"
        disabled={busy}
        aria-label="Export CSV"
        title="Export CSV"
        onClick={(event) => {
          event.stopPropagation();
          onCsv(batchId);
        }}
      >
        <FileSpreadsheet />
      </Button>
      <Button
        size="icon"
        variant="ghost"
        disabled={busy}
        aria-label="Export JSON"
        title="Export JSON"
        onClick={(event) => {
          event.stopPropagation();
          onJson(batchId);
        }}
      >
        <FileJson />
      </Button>
    </div>
  );
}

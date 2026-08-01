"use client";

import { Download, RefreshCw, Upload } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  EmptyState,
  EmptyStateAction,
  ErrorState,
  FilterBar,
  QuickActions,
  SearchInput,
} from "@/components/common";
import { PageContainer, PageHeader } from "@/components/layout";
import {
  useBatchExportResults,
  useCompletedJobs,
} from "@/features/benchmark/api";
import { BatchSelector } from "@/features/benchmark/components/batch-selector";
import { ComparisonTable } from "@/features/evaluation/components/comparison-table";
import { ConfusionMatrix } from "@/features/evaluation/components/confusion-matrix";
import { GroundTruthUploader } from "@/features/evaluation/components/ground-truth-uploader";
import { JsonComparison } from "@/features/evaluation/components/json-comparison";
import {
  EvaluationSummaryCards,
  PerFieldAccuracyTable,
} from "@/features/evaluation/components/summary-cards";
import {
  compareRows,
  emotionConfusion,
  summarize,
  type RowComparison,
} from "@/features/evaluation/lib/compare";
import { useDebounce } from "@/hooks/use-debounce";
import { ROUTES } from "@/lib/constants";
import { downloadBlob, downloadJson } from "@/lib/download";
import { notify } from "@/lib/notify";
import type { BatchExportResultRow } from "@/types/domain";

type FilterMode = "mismatches" | "low_confidence" | "failed" | null;

export function EvaluationStudio() {
  const jobsQuery = useCompletedJobs();
  const jobs = useMemo(() => jobsQuery.data?.items ?? [], [jobsQuery.data]);
  const [batchId, setBatchId] = useState<string | null>(null);
  const [expected, setExpected] = useState<BatchExportResultRow[]>([]);
  const [sourceName, setSourceName] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<FilterMode>(null);
  const [selected, setSelected] = useState<string | null>(null);

  const debouncedSearch = useDebounce(search, 250);
  const actualQuery = useBatchExportResults(batchId);

  useEffect(() => {
    if (!batchId && jobs[0]) setBatchId(jobs[0].batch_id);
  }, [jobs, batchId]);

  const comparisons = useMemo(() => {
    if (!expected.length || !actualQuery.data) return [];
    return compareRows(expected, actualQuery.data.results);
  }, [expected, actualQuery.data]);

  const summary = useMemo(
    () => (comparisons.length ? summarize(comparisons) : null),
    [comparisons],
  );

  const confusion = useMemo(
    () => emotionConfusion(comparisons),
    [comparisons],
  );

  const filtered = useMemo(() => {
    let rows = comparisons;
    const needle = debouncedSearch.trim().toLowerCase();
    if (needle) {
      rows = rows.filter((row) => row.filename.toLowerCase().includes(needle));
    }
    if (filter === "mismatches") {
      rows = rows.filter((row) => row.overall === "mismatch");
    } else if (filter === "low_confidence") {
      rows = rows.filter(
        (row) => row.confidence !== null && row.confidence < 0.6,
      );
    } else if (filter === "failed") {
      rows = rows.filter((row) => row.overall === "missing" || !row.actual);
    }
    return rows;
  }, [comparisons, debouncedSearch, filter]);

  const selectedRow: RowComparison | null = useMemo(
    () => filtered.find((row) => row.filename === selected) ?? filtered[0] ?? null,
    [filtered, selected],
  );

  function exportComparisonCsv() {
    const header = [
      "filename",
      "match",
      "confidence",
      "expected_json",
      "actual_json",
    ];
    const lines = [
      header.join(","),
      ...filtered.map((row) =>
        [
          JSON.stringify(row.filename),
          row.overall,
          row.confidence ?? "",
          JSON.stringify(JSON.stringify(row.expected)),
          JSON.stringify(JSON.stringify(row.actual)),
        ].join(","),
      ),
    ];
    downloadBlob(
      new Blob([lines.join("\n")], { type: "text/csv" }),
      `evaluation-${batchId ?? "batch"}.csv`,
    );
    notify.success("Comparison CSV downloaded");
  }

  function exportComparisonJson() {
    downloadJson(
      {
        batch_id: batchId,
        ground_truth_source: sourceName,
        summary,
        rows: filtered,
      },
      `evaluation-${batchId ?? "batch"}.json`,
    );
    notify.success("Comparison JSON downloaded");
  }

  return (
    <PageContainer className="max-w-7xl">
      <PageHeader
        title="Evaluation Studio"
        description="Compare expected assessment labels against pipeline predictions. Upload ground truth, pick a completed batch, inspect mismatches."
        actions={
          <QuickActions
            actions={[
              {
                id: "csv",
                label: "Export CSV",
                icon: Download,
                disabled: !filtered.length,
                onClick: exportComparisonCsv,
              },
              {
                id: "json",
                label: "Export JSON",
                icon: Download,
                disabled: !filtered.length,
                onClick: exportComparisonJson,
              },
              {
                id: "refresh",
                label: "Refresh",
                icon: RefreshCw,
                shortcut: "R",
                disabled: !batchId || actualQuery.isFetching,
                onClick: () => void actualQuery.refetch(),
              },
              {
                id: "upload",
                label: "Upload",
                icon: Upload,
                href: ROUTES.upload,
                shortcut: "U",
              },
            ]}
          />
        }
      />

      <div className="grid gap-4 lg:grid-cols-[1.1fr_1fr]">
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground">
            Actual predictions (batch)
          </p>
          <BatchSelector
            jobs={jobs}
            value={batchId}
            onChange={setBatchId}
            loading={jobsQuery.isLoading}
          />
          {actualQuery.isError ? (
            <ErrorState
              error={actualQuery.error}
              title="Failed to load batch predictions"
              onRetry={() => void actualQuery.refetch()}
            />
          ) : null}
          {actualQuery.data ? (
            <p className="text-xs text-muted-foreground">
              Loaded {actualQuery.data.count} predictions
              {sourceName ? ` · Ground truth: ${sourceName}` : ""}
            </p>
          ) : null}
        </div>
        <GroundTruthUploader
          onLoaded={(rows, source) => {
            setExpected(rows);
            setSourceName(source);
            setSelected(null);
            notify.success(`Loaded ${rows.length} expected labels`);
          }}
          onError={(message) => notify.error(message)}
        />
      </div>

      {!expected.length ? (
        <EmptyState
          title="Waiting for ground truth"
          description="Upload an expected-label CSV or JSON to start comparing against the selected batch."
          action={<EmptyStateAction label="Upload audio first" href={ROUTES.upload} />}
          hint="Press E to return here"
        />
      ) : !actualQuery.data && !actualQuery.isLoading ? (
        <EmptyState
          title="Select a completed batch"
          description="Pick a batch with exported predictions to evaluate against."
          action={<EmptyStateAction label="Open batches" href={ROUTES.batches} />}
          hint="Press B for Batch Explorer"
        />
      ) : (
        <>
          <EvaluationSummaryCards summary={summary} />

          <div className="flex flex-wrap items-center gap-2">
            <SearchInput
              value={search}
              onChange={setSearch}
              placeholder="Search filename…"
              className="w-full sm:w-64"
              aria-label="Search comparison rows"
            />
            <FilterBar
              options={[
                { value: "mismatches", label: "Only mismatches" },
                { value: "low_confidence", label: "Low confidence" },
                { value: "failed", label: "Missing / failed" },
              ]}
              value={filter}
              onChange={(value) => setFilter(value as FilterMode)}
              allLabel="All rows"
            />
            <span className="ml-auto text-xs tabular-nums text-muted-foreground">
              {filtered.length} / {comparisons.length} rows
            </span>
          </div>

          <div className="grid gap-4 xl:grid-cols-[1.4fr_1fr]">
            {summary ? <PerFieldAccuracyTable summary={summary} /> : null}
            <ConfusionMatrix
              labels={confusion.labels}
              matrix={confusion.matrix}
            />
          </div>

          <ComparisonTable
            rows={filtered}
            selected={selectedRow?.filename ?? null}
            onSelect={setSelected}
          />

          <JsonComparison row={selectedRow} />
        </>
      )}
    </PageContainer>
  );
}

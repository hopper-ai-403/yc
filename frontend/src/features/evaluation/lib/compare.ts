import { ASSESSMENT_FIELDS } from "@/lib/constants";
import type { AssessmentPrediction, BatchExportResultRow } from "@/types/domain";

export type AssessmentField = (typeof ASSESSMENT_FIELDS)[number];

export type MatchKind = "exact" | "close" | "mismatch" | "missing";

export interface FieldComparison {
  field: AssessmentField;
  expected: unknown;
  actual: unknown;
  match: MatchKind;
}

export interface RowComparison {
  filename: string;
  expected: AssessmentPrediction | null;
  actual: AssessmentPrediction | null;
  fields: FieldComparison[];
  exactCount: number;
  closeCount: number;
  mismatchCount: number;
  overall: MatchKind;
  confidence: number | null;
}

export interface EvaluationSummary {
  total: number;
  matched: number;
  close: number;
  mismatched: number;
  missing: number;
  overallAccuracy: number;
  agreement: number;
  averageConfidence: number | null;
  perFieldAccuracy: Record<AssessmentField, number>;
}

const CLOSE_INTENSITY: Record<string, string[]> = {
  LOW: ["MEDIUM"],
  MEDIUM: ["LOW", "HIGH"],
  HIGH: ["MEDIUM"],
};

const CLOSE_SEVERITY: Record<string, string[]> = {
  NONE: ["LOW"],
  LOW: ["NONE", "MEDIUM"],
  MEDIUM: ["LOW", "HIGH"],
  HIGH: ["MEDIUM"],
};

const CLOSE_QUALITY: Record<string, string[]> = {
  CLEAR: ["SLIGHTLY_IMPAIRED"],
  SLIGHTLY_IMPAIRED: ["CLEAR", "SEVERELY_IMPAIRED"],
  SEVERELY_IMPAIRED: ["SLIGHTLY_IMPAIRED"],
};

function compareField(
  field: AssessmentField,
  expected: unknown,
  actual: unknown,
): MatchKind {
  if (expected === undefined || actual === undefined) return "missing";
  if (expected === actual) return "exact";

  if (field === "confidence") {
    const delta = Math.abs(Number(expected) - Number(actual));
    if (!Number.isFinite(delta)) return "mismatch";
    if (delta <= 0.05) return "exact";
    if (delta <= 0.15) return "close";
    return "mismatch";
  }

  if (field === "emotional_intensity") {
    const neighbors = CLOSE_INTENSITY[String(expected)] ?? [];
    return neighbors.includes(String(actual)) ? "close" : "mismatch";
  }
  if (field === "background_noise_severity") {
    const neighbors = CLOSE_SEVERITY[String(expected)] ?? [];
    return neighbors.includes(String(actual)) ? "close" : "mismatch";
  }
  if (field === "audio_quality") {
    const neighbors = CLOSE_QUALITY[String(expected)] ?? [];
    return neighbors.includes(String(actual)) ? "close" : "mismatch";
  }

  return "mismatch";
}

export function compareRows(
  expectedRows: BatchExportResultRow[],
  actualRows: BatchExportResultRow[],
): RowComparison[] {
  const actualByName = new Map(
    actualRows.map((row) => [row.filename.toLowerCase(), row]),
  );
  const expectedNames = new Set(
    expectedRows.map((row) => row.filename.toLowerCase()),
  );

  const comparisons: RowComparison[] = expectedRows.map((expected) => {
    const actual = actualByName.get(expected.filename.toLowerCase());
    const fields: FieldComparison[] = ASSESSMENT_FIELDS.map((field) => {
      const expectedValue = expected.result[field];
      const actualValue = actual?.result[field];
      return {
        field,
        expected: expectedValue,
        actual: actualValue,
        match: compareField(field, expectedValue, actualValue),
      };
    });
    const exactCount = fields.filter((f) => f.match === "exact").length;
    const closeCount = fields.filter((f) => f.match === "close").length;
    const mismatchCount = fields.filter((f) => f.match === "mismatch").length;
    let overall: MatchKind = "exact";
    if (!actual) overall = "missing";
    else if (mismatchCount > 0) overall = "mismatch";
    else if (closeCount > 0) overall = "close";

    return {
      filename: expected.filename,
      expected: expected.result,
      actual: actual?.result ?? null,
      fields,
      exactCount,
      closeCount,
      mismatchCount,
      overall,
      confidence: actual?.result.confidence ?? null,
    };
  });

  for (const actual of actualRows) {
    if (!expectedNames.has(actual.filename.toLowerCase())) {
      comparisons.push({
        filename: actual.filename,
        expected: null,
        actual: actual.result,
        fields: ASSESSMENT_FIELDS.map((field) => ({
          field,
          expected: undefined,
          actual: actual.result[field],
          match: "missing" as const,
        })),
        exactCount: 0,
        closeCount: 0,
        mismatchCount: 0,
        overall: "missing",
        confidence: actual.result.confidence,
      });
    }
  }

  return comparisons.sort((a, b) => a.filename.localeCompare(b.filename));
}

export function summarize(rows: RowComparison[]): EvaluationSummary {
  const comparable = rows.filter((row) => row.expected && row.actual);
  const matched = comparable.filter((row) => row.overall === "exact").length;
  const close = comparable.filter((row) => row.overall === "close").length;
  const mismatched = comparable.filter((row) => row.overall === "mismatch").length;
  const missing = rows.filter((row) => row.overall === "missing").length;

  const perFieldAccuracy = Object.fromEntries(
    ASSESSMENT_FIELDS.map((field) => {
      const fieldRows = comparable.map(
        (row) => row.fields.find((item) => item.field === field)!,
      );
      const hits = fieldRows.filter(
        (item) => item.match === "exact" || item.match === "close",
      ).length;
      return [field, fieldRows.length ? hits / fieldRows.length : 0];
    }),
  ) as Record<AssessmentField, number>;

  const confidences = comparable
    .map((row) => row.confidence)
    .filter((value): value is number => value !== null);

  return {
    total: rows.length,
    matched,
    close,
    mismatched,
    missing,
    overallAccuracy: comparable.length ? matched / comparable.length : 0,
    agreement: comparable.length
      ? (matched + close) / comparable.length
      : 0,
    averageConfidence: confidences.length
      ? confidences.reduce((a, b) => a + b, 0) / confidences.length
      : null,
    perFieldAccuracy,
  };
}

export function emotionConfusion(
  rows: RowComparison[],
): { labels: string[]; matrix: number[][] } {
  const pairs = rows.filter((row) => row.expected && row.actual);
  const labels = [
    ...new Set(
      pairs.flatMap((row) => [
        row.expected!.emotional_tone,
        row.actual!.emotional_tone,
      ]),
    ),
  ].sort();
  const index = new Map(labels.map((label, i) => [label, i]));
  const matrix = labels.map(() => labels.map(() => 0));
  for (const row of pairs) {
    const r = index.get(row.expected!.emotional_tone);
    const c = index.get(row.actual!.emotional_tone);
    if (r !== undefined && c !== undefined) matrix[r][c] += 1;
  }
  return { labels, matrix };
}

export function parseGroundTruth(text: string): BatchExportResultRow[] {
  const trimmed = text.trim();
  if (!trimmed) return [];

  if (trimmed.startsWith("[") || trimmed.startsWith("{")) {
    const parsed: unknown = JSON.parse(trimmed);
    const rows = Array.isArray(parsed)
      ? parsed
      : Array.isArray((parsed as { results?: unknown }).results)
        ? (parsed as { results: unknown[] }).results
        : null;
    if (!rows) {
      throw new Error(
        "JSON must be an array of {filename, result} or {results: [...]}",
      );
    }
    return rows.map((row, index) => {
      const item = row as {
        filename?: string;
        result?: AssessmentPrediction;
        result_json?: AssessmentPrediction | string;
      };
      const filename = item.filename;
      let result = item.result;
      if (!result && item.result_json) {
        result =
          typeof item.result_json === "string"
            ? (JSON.parse(item.result_json) as AssessmentPrediction)
            : item.result_json;
      }
      if (!filename || !result) {
        throw new Error(`Invalid ground-truth row at index ${index}`);
      }
      return { filename, result };
    });
  }

  // CSV: filename,result_json
  const lines = trimmed.split(/\r?\n/).filter(Boolean);
  if (lines.length < 2) throw new Error("CSV requires a header and at least one row");
  const header = lines[0].toLowerCase();
  if (!header.includes("filename") || !header.includes("result")) {
    throw new Error("CSV header must include filename and result_json");
  }
  return lines.slice(1).map((line, index) => {
    const comma = line.indexOf(",");
    if (comma < 0) throw new Error(`Malformed CSV row ${index + 2}`);
    let filename = line.slice(0, comma).trim();
    let payload = line.slice(comma + 1).trim();
    if (filename.startsWith('"') && filename.endsWith('"')) {
      filename = filename.slice(1, -1);
    }
    if (payload.startsWith('"') && payload.endsWith('"')) {
      payload = payload.slice(1, -1).replace(/""/g, '"');
    }
    return {
      filename,
      result: JSON.parse(payload) as AssessmentPrediction,
    };
  });
}

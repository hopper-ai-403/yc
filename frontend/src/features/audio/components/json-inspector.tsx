"use client";

import dynamic from "next/dynamic";
import { useMemo, useState } from "react";
import type { UseQueryResult } from "@tanstack/react-query";

import { CopyButton } from "@/components/common/copy-button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

import {
  useAudioAcoustic,
  useAudioAnalysis,
  useAudioAsset,
  useAudioPrediction,
  useAudioSpeech,
  useAudioTechnical,
} from "../api";
import { SectionBody, SectionCard } from "./section";

const JsonViewer = dynamic(
  () =>
    import("@/components/common/json-viewer").then((mod) => mod.JsonViewer),
  { ssr: false, loading: () => <Skeleton className="h-40 w-full" /> },
);

export const INSPECTOR_TABS = [
  "prediction",
  "technical",
  "acoustic",
  "speech",
  "analysis",
  "internal",
] as const;

export type InspectorTab = (typeof INSPECTOR_TABS)[number];

function matchesQuery(value: unknown, query: string): boolean {
  if (typeof value === "object" && value !== null) {
    return Object.entries(value as Record<string, unknown>).some(
      ([key, item]) =>
        key.toLowerCase().includes(query) || matchesQuery(item, query),
    );
  }
  return false;
}

function filterJson(value: unknown, query: string): unknown {
  if (!query || typeof value !== "object" || value === null) return value;
  if (Array.isArray(value)) {
    return value.filter((item) => matchesQuery(item, query));
  }
  return Object.fromEntries(
    Object.entries(value as Record<string, unknown>)
      .filter(
        ([key, item]) =>
          key.toLowerCase().includes(query) || matchesQuery(item, query),
      )
      .map(([key, item]) => [
        key,
        key.toLowerCase().includes(query) ? item : filterJson(item, query),
      ]),
  );
}

export function JsonInspector({
  audioId,
  tab,
  onTabChange,
}: {
  audioId: string;
  tab: InspectorTab;
  onTabChange: (tab: InspectorTab) => void;
}) {
  const [search, setSearch] = useState("");
  const prediction = useAudioPrediction(audioId);
  const technical = useAudioTechnical(audioId);
  const acoustic = useAudioAcoustic(audioId);
  const speech = useAudioSpeech(audioId);
  const analysis = useAudioAnalysis(audioId);
  const asset = useAudioAsset(audioId);

  const tabQuery: Record<InspectorTab, UseQueryResult<unknown>> = {
    prediction,
    technical,
    acoustic,
    speech,
    analysis,
    internal: asset,
  };

  const activeQuery = tabQuery[tab];
  const activeData = useMemo(() => {
    const data = activeQuery.data;
    if (tab === "internal") {
      const timing =
        (data as { timing_json?: Record<string, unknown> | null } | undefined)
          ?.timing_json ?? null;
      const payload = { timing_json: timing };
      return search ? filterJson(payload, search.toLowerCase()) : payload;
    }
    return search ? filterJson(data, search.toLowerCase()) : data;
  }, [activeQuery.data, tab, search]);

  return (
    <SectionCard
      title="JSON Inspector"
      description="Raw pipeline payloads"
      actions={
        activeQuery.data ? (
          <CopyButton
            size="icon"
            value={JSON.stringify(activeQuery.data, null, 2)}
          />
        ) : null
      }
    >
      <div className="space-y-3">
        <div
          role="tablist"
          aria-label="JSON payload tabs"
          className="flex flex-wrap gap-1"
        >
          {INSPECTOR_TABS.map((item) => (
            <button
              key={item}
              type="button"
              role="tab"
              aria-selected={tab === item}
              onClick={() => onTabChange(item)}
              className={cn(
                "rounded-md px-2 py-1 text-xs capitalize transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                tab === item
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground",
              )}
            >
              {item}
            </button>
          ))}
        </div>
        <Input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Filter keys…"
          aria-label="Filter JSON keys"
          className="h-8 text-xs"
        />
        <SectionBody query={activeQuery} pendingLabel={`${tab} payload`}>
          {() => (
            <JsonViewer
              data={activeData}
              defaultOpenDepth={2}
              className="max-h-96"
            />
          )}
        </SectionBody>
      </div>
    </SectionCard>
  );
}

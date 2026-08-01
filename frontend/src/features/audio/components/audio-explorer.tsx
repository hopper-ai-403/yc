"use client";

import {
  ArrowLeft,
  Copy,
  Eye,
  Gauge,
  RefreshCw,
} from "lucide-react";
import { useEffect, useState } from "react";

import { ErrorState } from "@/components/common/error-state";
import { QuickActions } from "@/components/common/quick-actions";
import { StatusBadge } from "@/components/common/status-badge";
import { PageContainer } from "@/components/layout/page-container";
import { PageHeader } from "@/components/layout/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { useCopyToClipboard } from "@/hooks/use-copy-to-clipboard";
import { ROUTES } from "@/lib/constants";
import { notify } from "@/lib/notify";
import { useUiStore } from "@/stores/ui-store";

import {
  useAudioAsset,
  useAudioAcoustic,
  useAudioPrediction,
  useAudioSpeech,
  useAudioTechnical,
} from "../api";
import { ArtifactsPanel } from "./artifacts-panel";
import {
  AcousticIntelligenceCard,
  SpeechIntelligenceCard,
  TechnicalIntelligenceCard,
} from "./intelligence-cards";
import { JsonInspector, type InspectorTab } from "./json-inspector";
import { MetadataCard } from "./metadata-card";
import { PipelineTimeline } from "./pipeline-timeline";
import { PlayerPanel } from "./player-panel";
import { PredictionCard } from "./prediction-card";
import { ConfidencePanel, TimingPanel } from "./timing-panel";

export function AudioExplorer({ audioId }: { audioId: string }) {
  const [inspectorTab, setInspectorTab] = useState<InspectorTab>("prediction");
  const openDrawer = useUiStore((s) => s.openDrawer);
  const { copy } = useCopyToClipboard();
  const asset = useAudioAsset(audioId);
  const technical = useAudioTechnical(audioId);
  const acoustic = useAudioAcoustic(audioId);
  const speech = useAudioSpeech(audioId);
  const prediction = useAudioPrediction(audioId);

  useEffect(() => {
    function onRefresh() {
      void asset.refetch();
      void technical.refetch();
      void acoustic.refetch();
      void speech.refetch();
      void prediction.refetch();
    }
    window.addEventListener("aip:refresh", onRefresh);
    return () => window.removeEventListener("aip:refresh", onRefresh);
  }, [asset, technical, acoustic, speech, prediction]);

  if (asset.isError) {
    return (
      <PageContainer>
        <PageHeader title="Audio Intelligence Explorer" />
        <ErrorState
          error={asset.error}
          title="Failed to load audio asset"
          onRetry={() => void asset.refetch()}
        />
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <PageHeader
        title={asset.data?.filename ?? "Audio Intelligence Explorer"}
        description={`Audio ${audioId}`}
        actions={
          asset.data ? (
            <>
              <StatusBadge status={asset.data.processing_status} />
              <QuickActions
                actions={[
                  {
                    id: "prediction",
                    label: "Prediction",
                    icon: Eye,
                    onClick: () =>
                      openDrawer({
                        kind: "prediction",
                        id: audioId,
                        title: asset.data?.filename,
                      }),
                  },
                  {
                    id: "metadata",
                    label: "Metadata",
                    icon: Eye,
                    onClick: () =>
                      openDrawer({
                        kind: "metadata",
                        id: audioId,
                        title: asset.data?.filename,
                      }),
                  },
                  {
                    id: "copy",
                    label: "Copy ID",
                    icon: Copy,
                    onClick: () => {
                      void copy(audioId).then((ok) => {
                        if (ok) notify.success("Audio ID copied");
                      });
                    },
                  },
                  {
                    id: "refresh",
                    label: "Refresh",
                    icon: RefreshCw,
                    shortcut: "R",
                    disabled: asset.isFetching,
                    onClick: () => void asset.refetch(),
                  },
                  {
                    id: "benchmark",
                    label: "Benchmark",
                    icon: Gauge,
                    href: `${ROUTES.benchmark}?batch=${asset.data.batch_id}`,
                    shortcut: "G",
                  },
                  {
                    id: "batch",
                    label: "Batch",
                    icon: ArrowLeft,
                    href: ROUTES.batchDetail(asset.data.batch_id),
                    shortcut: "B",
                  },
                ]}
              />
            </>
          ) : (
            <Skeleton className="h-8 w-48" />
          )
        }
      />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-[1.05fr_1.2fr_0.95fr]">
        <div className="space-y-4">
          <PlayerPanel audioId={audioId} />
          <MetadataCard audioId={audioId} />
        </div>
        <div className="space-y-4">
          {asset.data ? (
            <PipelineTimeline
              asset={asset.data}
              technical={technical.data}
              acoustic={acoustic.data}
              speech={speech.data}
              prediction={prediction.data}
            />
          ) : (
            <Skeleton className="h-72 w-full" />
          )}
          <TechnicalIntelligenceCard audioId={audioId} />
          <AcousticIntelligenceCard audioId={audioId} />
          <SpeechIntelligenceCard audioId={audioId} />
          <PredictionCard audioId={audioId} />
        </div>
        <div className="space-y-4 lg:col-span-2 xl:col-span-1">
          <JsonInspector
            audioId={audioId}
            tab={inspectorTab}
            onTabChange={setInspectorTab}
          />
          <TimingPanel audioId={audioId} />
          <ConfidencePanel audioId={audioId} />
          <ArtifactsPanel audioId={audioId} onViewTab={setInspectorTab} />
        </div>
      </div>
    </PageContainer>
  );
}

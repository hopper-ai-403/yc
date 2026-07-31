"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { useState } from "react";

import { ErrorState } from "@/components/common/error-state";
import { StatusBadge } from "@/components/common/status-badge";
import { PageContainer } from "@/components/layout/page-container";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ROUTES } from "@/lib/constants";

import { useAudioAsset, useAudioAcoustic, useAudioPrediction, useAudioSpeech, useAudioTechnical } from "../api";
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
  const asset = useAudioAsset(audioId);
  const technical = useAudioTechnical(audioId);
  const acoustic = useAudioAcoustic(audioId);
  const speech = useAudioSpeech(audioId);
  const prediction = useAudioPrediction(audioId);

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
              <Link href={ROUTES.batchDetail(asset.data.batch_id)}>
                <Button variant="outline" size="sm">
                  <ArrowLeft />
                  Batch
                </Button>
              </Link>
            </>
          ) : (
            <Skeleton className="h-8 w-32" />
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

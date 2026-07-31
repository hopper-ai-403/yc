import { useQuery } from "@tanstack/react-query";

import { audioKeys } from "./keys";

import { ApiError } from "@/services/client";
import { audioApi } from "@/services/audio";
import { predictionApi } from "@/services/prediction";
import { QUERY_STALE_TIME_MS } from "@/lib/constants";
import { AUDIO_DETAIL_REFETCH_MS } from "./constants";

function shouldRetry(failureCount: number, error: Error): boolean {
  if (error instanceof ApiError && error.status === 404) return false;
  return failureCount < 2;
}

export function useAudioAsset(audioId: string) {
  return useQuery({
    queryKey: audioKeys.detail(audioId),
    queryFn: () => audioApi.getAudioAsset(audioId),
    staleTime: QUERY_STALE_TIME_MS,
    retry: shouldRetry,
    refetchInterval: (query) => {
      const status = query.state.data?.processing_status;
      return status === "QUEUED" || status === "PROCESSING"
        ? AUDIO_DETAIL_REFETCH_MS
        : false;
    },
  });
}

export function useAudioMetadata(audioId: string) {
  return useQuery({
    queryKey: audioKeys.metadata(audioId),
    queryFn: () => audioApi.getAudioMetadata(audioId),
    staleTime: Infinity,
    retry: shouldRetry,
  });
}

export function useAudioDownload(audioId: string) {
  return useQuery({
    queryKey: audioKeys.download(audioId),
    queryFn: () => audioApi.getAudioDownload(audioId),
    staleTime: QUERY_STALE_TIME_MS,
    retry: shouldRetry,
  });
}

export function useAudioAnalysis(audioId: string) {
  return useQuery({
    queryKey: audioKeys.analysis(audioId),
    queryFn: () => audioApi.getAudioAnalysis(audioId),
    staleTime: Infinity,
    retry: shouldRetry,
  });
}

export function useAudioSegments(audioId: string) {
  return useQuery({
    queryKey: audioKeys.segments(audioId),
    queryFn: () => audioApi.getAudioSegments(audioId),
    staleTime: Infinity,
    retry: shouldRetry,
  });
}

export function useAudioTechnical(audioId: string) {
  return useQuery({
    queryKey: audioKeys.technical(audioId),
    queryFn: () => audioApi.getAudioTechnical(audioId),
    staleTime: Infinity,
    retry: shouldRetry,
  });
}

export function useAudioAcoustic(audioId: string) {
  return useQuery({
    queryKey: audioKeys.acoustic(audioId),
    queryFn: () => audioApi.getAudioAcoustic(audioId),
    staleTime: Infinity,
    retry: shouldRetry,
  });
}

export function useAudioSpeech(audioId: string) {
  return useQuery({
    queryKey: audioKeys.speech(audioId),
    queryFn: () => audioApi.getAudioSpeech(audioId),
    staleTime: Infinity,
    retry: shouldRetry,
  });
}

export function useAudioPrediction(audioId: string) {
  return useQuery({
    queryKey: [...audioKeys.detail(audioId), "prediction"] as const,
    queryFn: () => predictionApi.getAudioPrediction(audioId),
    staleTime: Infinity,
    retry: shouldRetry,
  });
}

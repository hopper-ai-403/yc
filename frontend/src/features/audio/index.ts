import { audioApi } from "@/services/audio";
import { createQueryKeys } from "@/features/shared/query-keys";

const keys = createQueryKeys("audio");

export const audioKeys = {
  ...keys,
  metadata: (id: string) => [...keys.detail(id), "metadata"] as const,
  download: (id: string) => [...keys.detail(id), "download"] as const,
  analysis: (id: string) => [...keys.detail(id), "analysis"] as const,
  segments: (id: string) => [...keys.detail(id), "segments"] as const,
  technical: (id: string) => [...keys.detail(id), "technical"] as const,
  acoustic: (id: string) => [...keys.detail(id), "acoustic"] as const,
  speech: (id: string) => [...keys.detail(id), "speech"] as const,
};

export { audioApi };
export type {
  AudioAcousticRead,
  AudioAnalysisRead,
  AudioAssetRead,
  AudioDownloadData,
  AudioSegmentsRead,
  AudioSpeechRead,
  AudioTechnicalRead,
} from "@/types/domain";

import { predictionApi } from "@/services/prediction";

export const predictionKeys = {
  byAudio: (audioId: string) => ["predictions", "audio", audioId] as const,
  byBatch: (batchId: string) => ["predictions", "batch", batchId] as const,
  byJob: (jobId: string) => ["predictions", "job", jobId] as const,
};

export { predictionApi };
export type {
  AssessmentPrediction,
  PredictionListRead,
  PredictionRead,
} from "@/types/domain";

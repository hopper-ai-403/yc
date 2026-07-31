import { get } from "./client";

import type { PredictionListRead, PredictionRead } from "@/types/domain";

export async function getAudioPrediction(audioId: string): Promise<PredictionRead> {
  return get<PredictionRead>(`/audio/${audioId}/prediction`);
}

export async function getBatchPredictions(
  batchId: string,
): Promise<PredictionListRead> {
  return get<PredictionListRead>(`/batches/${batchId}/predictions`);
}

export async function getJobPredictions(jobId: string): Promise<PredictionListRead> {
  return get<PredictionListRead>(`/jobs/${jobId}/predictions`);
}

export const predictionApi = {
  getAudioPrediction,
  getBatchPredictions,
  getJobPredictions,
};

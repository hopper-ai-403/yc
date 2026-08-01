import { get, post, del, rawClient } from "./client";

import type {
  BatchDeleteRead,
  BatchExportJsonRead,
  BatchExportsRead,
  BatchMetricsRead,
  BatchRunRead,
  BatchStatusRead,
  JobActionData,
  JobListData,
  JobProgressData,
  JobRead,
  JobStatus,
  StartJobData,
} from "@/types/domain";

// ---------- Batch orchestration (evaluation) ----------

export async function runBatch(batchId: string): Promise<BatchRunRead> {
  return post<BatchRunRead>(`/batches/${batchId}/run`);
}

export async function deleteBatch(batchId: string): Promise<BatchDeleteRead> {
  return del<BatchDeleteRead>(`/batches/${batchId}`);
}

export async function getBatchStatus(batchId: string): Promise<BatchStatusRead> {
  return get<BatchStatusRead>(`/batches/${batchId}/status`);
}

export async function getBatchMetrics(batchId: string): Promise<BatchMetricsRead> {
  return get<BatchMetricsRead>(`/batches/${batchId}/metrics`);
}

export async function getBatchExports(batchId: string): Promise<BatchExportsRead> {
  return get<BatchExportsRead>(`/batches/${batchId}/exports`);
}

export async function getBatchExportJson(
  batchId: string,
): Promise<BatchExportJsonRead> {
  return get<BatchExportJsonRead>(`/batches/${batchId}/export/json`);
}

/** Download the assessment CSV (non-envelope endpoint). */
export async function downloadBatchCsv(batchId: string): Promise<Blob> {
  const response = await rawClient().get(`/batches/${batchId}/export/csv`, {
    responseType: "blob",
  });
  return response.data as Blob;
}

// ---------- Jobs ----------

export async function listJobs(params?: {
  status?: JobStatus;
  limit?: number;
  offset?: number;
}): Promise<JobListData> {
  return get<JobListData>("/jobs", { params });
}

export async function getJob(jobId: string): Promise<JobRead> {
  return get<JobRead>(`/jobs/${jobId}`);
}

export async function getJobProgress(jobId: string): Promise<JobProgressData> {
  return get<JobProgressData>(`/jobs/${jobId}/progress`);
}

export async function startJob(jobId: string): Promise<StartJobData> {
  return post<StartJobData>(`/jobs/${jobId}/start`);
}

export async function retryJob(jobId: string): Promise<JobActionData> {
  return post<JobActionData>(`/jobs/${jobId}/retry`);
}

export async function cancelJob(jobId: string): Promise<JobActionData> {
  return post<JobActionData>(`/jobs/${jobId}/cancel`);
}

export const batchApi = {
  runBatch,
  deleteBatch,
  getBatchStatus,
  getBatchMetrics,
  getBatchExports,
  getBatchExportJson,
  downloadBatchCsv,
};

export const jobsApi = {
  listJobs,
  getJob,
  getJobProgress,
  startJob,
  retryJob,
  cancelJob,
};

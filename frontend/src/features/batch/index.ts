import { batchApi, jobsApi } from "@/services/batch";
import { createQueryKeys } from "@/features/shared/query-keys";

const keys = createQueryKeys("batches");

export const batchKeys = {
  ...keys,
  status: (id: string) => [...keys.detail(id), "status"] as const,
  metrics: (id: string) => [...keys.detail(id), "metrics"] as const,
  exports: (id: string) => [...keys.detail(id), "exports"] as const,
  predictions: (id: string) => [...keys.detail(id), "predictions"] as const,
  jobProgress: (jobId: string) => ["jobs", "progress", jobId] as const,
};

export { batchApi, jobsApi };
export type {
  BatchExportsRead,
  BatchMetricsRead,
  BatchRunRead,
  BatchStatusRead,
  JobProgressData,
  JobRead,
} from "@/types/domain";

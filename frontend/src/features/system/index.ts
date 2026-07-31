import { systemApi } from "@/services/system";
import { createQueryKeys } from "@/features/shared/query-keys";

const keys = createQueryKeys("system");

export const systemKeys = {
  ...keys,
  metrics: () => [...keys.all, "metrics"] as const,
  workers: () => [...keys.all, "workers"] as const,
  readiness: () => [...keys.all, "readiness"] as const,
};

export { systemApi };
export type {
  ComponentHealth,
  ReadinessData,
  SystemMetricsRead,
  WorkerRead,
  WorkersRead,
} from "@/types/domain";

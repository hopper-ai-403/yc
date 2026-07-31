import { jobsApi } from "@/services/batch";
import { systemApi } from "@/services/system";
import { createQueryKeys } from "@/features/shared/query-keys";

export const dashboardKeys = {
  jobs: createQueryKeys("jobs"),
  system: createQueryKeys("system"),
};

export { jobsApi, systemApi };

import { benchmarkApi } from "@/services/benchmark";

export const benchmarkKeys = {
  byBatch: (batchId: string) => ["benchmark", batchId] as const,
};

export { benchmarkApi };
export type { BenchmarkRead } from "@/types/domain";

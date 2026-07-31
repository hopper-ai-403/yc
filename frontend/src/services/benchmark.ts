import { get } from "./client";

import type { BenchmarkRead } from "@/types/domain";

export async function getBatchBenchmark(batchId: string): Promise<BenchmarkRead> {
  return get<BenchmarkRead>("/system/benchmark", {
    params: { batch_id: batchId },
  });
}

export const benchmarkApi = { getBatchBenchmark };

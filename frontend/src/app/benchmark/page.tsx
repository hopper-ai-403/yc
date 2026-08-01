import type { Metadata } from "next";
import { Suspense } from "react";

import { PageContainer } from "@/components/layout";
import { Skeleton } from "@/components/ui/skeleton";
import { BenchmarkDashboard } from "@/features/benchmark";

export const metadata: Metadata = {
  title: "Benchmark",
};

function BenchmarkFallback() {
  return (
    <PageContainer className="max-w-7xl space-y-4">
      <Skeleton className="h-10 w-64" />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        {Array.from({ length: 9 }, (_, index) => (
          <Skeleton key={index} className="h-24 w-full" />
        ))}
      </div>
    </PageContainer>
  );
}

export default function BenchmarkPage() {
  return (
    <Suspense fallback={<BenchmarkFallback />}>
      <BenchmarkDashboard />
    </Suspense>
  );
}

import { LoadingBlock } from "@/components/common/loading-spinner";
import { PageContainer } from "@/components/layout";
import { Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
  return (
    <PageContainer>
      <div className="space-y-2 border-b border-border pb-4">
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-4 w-96" />
      </div>
      <LoadingBlock />
    </PageContainer>
  );
}

"use client";

import { FileQuestion } from "lucide-react";

import { EmptyState, EmptyStateAction } from "@/components/common/empty-state";
import { PageContainer } from "@/components/layout";
import { ROUTES } from "@/lib/constants";

export default function NotFound() {
  return (
    <PageContainer className="pt-16">
      <EmptyState
        icon={FileQuestion}
        title="404 — Page not found"
        description="The page you are looking for does not exist or has been moved."
        action={
          <EmptyStateAction label="Return to dashboard" href={ROUTES.dashboard} />
        }
        hint="Ctrl+K to search pages and batches"
      />
    </PageContainer>
  );
}

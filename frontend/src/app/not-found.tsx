import { FileQuestion } from "lucide-react";
import Link from "next/link";

import { EmptyState } from "@/components/common/empty-state";
import { PageContainer } from "@/components/layout";
import { buttonVariants } from "@/components/ui/button";
import { ROUTES } from "@/lib/constants";

export default function NotFound() {
  return (
    <PageContainer className="pt-16">
      <EmptyState
        icon={FileQuestion}
        title="404 — Page not found"
        description="The page you are looking for does not exist or has been moved."
        action={
          <Link href={ROUTES.dashboard} className={buttonVariants({ size: "sm", variant: "outline" })}>
            Return to dashboard
          </Link>
        }
      />
    </PageContainer>
  );
}

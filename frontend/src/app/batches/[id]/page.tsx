import type { Metadata } from "next";

import { BatchDetailView } from "@/features/batch";

export const metadata: Metadata = {
  title: "Batch Detail",
};

export default async function BatchDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <BatchDetailView batchId={id} />;
}

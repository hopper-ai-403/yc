import type { Metadata } from "next";

import { BatchExplorer } from "@/features/batch";

export const metadata: Metadata = {
  title: "Batches",
};

export default function BatchesPage() {
  return <BatchExplorer />;
}

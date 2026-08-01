import type { Metadata } from "next";

import { EvaluationStudio } from "@/features/evaluation";

export const metadata: Metadata = {
  title: "Evaluation Studio",
};

export default function EvaluationPage() {
  return <EvaluationStudio />;
}

import type { Metadata } from "next";

import { UploadStudio } from "@/features/upload";

export const metadata: Metadata = {
  title: "Upload Studio",
};

export default function UploadPage() {
  return <UploadStudio />;
}

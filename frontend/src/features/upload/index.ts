import { uploadApi } from "@/services/upload";

export const uploadKeys = {
  all: ["uploads"] as const,
};

export { uploadApi };
export type { UploadOptions } from "@/services/upload";
export type { RejectedFile, UploadResultData } from "@/types/domain";

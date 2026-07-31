"use client";

import { ArrowRight, CheckCircle2 } from "lucide-react";
import Link from "next/link";
import { motion } from "framer-motion";

import { CopyButton } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ROUTES } from "@/lib/constants";
import type { UploadResultData } from "@/types/domain";

interface UploadSuccessProps {
  result: UploadResultData;
  onReset: () => void;
}

export function UploadSuccess({ result, onReset }: UploadSuccessProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
    >
      <Card className="border-success/30">
        <CardContent className="space-y-4 p-4">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="size-4 text-success" />
            <p className="text-sm font-medium text-foreground">
              Batch created — {result.files_uploaded}{" "}
              {result.files_uploaded === 1 ? "file" : "files"} accepted
            </p>
          </div>

          <dl className="grid grid-cols-1 gap-2 text-xs sm:grid-cols-2">
            <div>
              <dt className="text-muted-foreground">Batch ID</dt>
              <dd className="mt-0.5 flex items-center gap-2">
                <span className="font-mono text-foreground">{result.batch_id}</span>
                <CopyButton value={result.batch_id} size="icon" className="size-6" />
              </dd>
            </div>
            {result.files_rejected > 0 ? (
              <div>
                <dt className="text-muted-foreground">Rejected by server</dt>
                <dd className="mt-0.5 font-mono text-warning">
                  {result.files_rejected}
                </dd>
              </div>
            ) : null}
          </dl>

          {result.rejected_files.length > 0 ? (
            <ul className="space-y-1 rounded-lg border border-warning/30 bg-warning/5 p-3 text-xs">
              {result.rejected_files.map((file) => (
                <li key={file.filename} className="flex justify-between gap-4">
                  <span className="truncate font-mono text-foreground">
                    {file.filename}
                  </span>
                  <span className="shrink-0 text-warning">{file.reason}</span>
                </li>
              ))}
            </ul>
          ) : null}

          <div className="flex flex-wrap items-center gap-2">
            <Link href={ROUTES.batchDetail(result.batch_id)}>
              <Button size="sm">
                Open Batch
                <ArrowRight />
              </Button>
            </Link>
            <Button size="sm" variant="outline" onClick={onReset}>
              Upload another batch
            </Button>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}

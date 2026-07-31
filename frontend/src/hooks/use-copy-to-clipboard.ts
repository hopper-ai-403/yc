"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export function useCopyToClipboard(resetDelayMs = 2000): {
  copied: boolean;
  copy: (text: string) => Promise<boolean>;
} {
  const [copied, setCopied] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, []);

  const copy = useCallback(
    async (text: string) => {
      try {
        await navigator.clipboard.writeText(text);
        setCopied(true);
        if (timer.current) clearTimeout(timer.current);
        timer.current = setTimeout(() => setCopied(false), resetDelayMs);
        return true;
      } catch {
        setCopied(false);
        return false;
      }
    },
    [resetDelayMs],
  );

  return { copied, copy };
}

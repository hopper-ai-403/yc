"use client";

import { useEffect, useState } from "react";

/** True after first client render; guards hydration-sensitive UI. */
export function useMounted(): boolean {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  return mounted;
}

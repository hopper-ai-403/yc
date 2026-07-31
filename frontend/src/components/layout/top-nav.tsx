"use client";

import { useQuery } from "@tanstack/react-query";
import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";

import { HealthBadge } from "@/components/common/health-badge";
import { Button } from "@/components/ui/button";
import { useMounted } from "@/hooks/use-mounted";
import { SYSTEM_METRICS_REFETCH_MS } from "@/lib/constants";
import { systemApi } from "@/services/system";
import type { HealthState } from "@/types/domain";

function SystemHealthIndicator() {
  const { data, isError } = useQuery({
    queryKey: ["system", "health"],
    queryFn: systemApi.getHealth,
    refetchInterval: SYSTEM_METRICS_REFETCH_MS,
    retry: false,
  });

  const status: HealthState = isError
    ? "unhealthy"
    : (data?.status ?? "degraded");

  return <HealthBadge status={status} label={data ? "API" : "API"} />;
}

function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const mounted = useMounted();
  if (!mounted) {
    return <Button variant="ghost" size="icon" aria-label="Toggle theme" />;
  }
  const dark = theme !== "light";
  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
      onClick={() => setTheme(dark ? "light" : "dark")}
    >
      {dark ? <Sun /> : <Moon />}
    </Button>
  );
}

export function TopNav() {
  return (
    <header className="sticky top-0 z-30 flex h-14 items-center justify-end gap-3 border-b border-border bg-background/80 px-4 backdrop-blur">
      <SystemHealthIndicator />
      <ThemeToggle />
    </header>
  );
}

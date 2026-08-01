"use client";

import { useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  Gauge,
  RefreshCw,
  Search,
  Upload,
} from "lucide-react";
import { useTheme } from "next-themes";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { HealthBadge } from "@/components/common/health-badge";
import { Button } from "@/components/ui/button";
import { useKeyboardShortcuts } from "@/hooks/use-keyboard-shortcuts";
import { useMounted } from "@/hooks/use-mounted";
import { ROUTES, SYSTEM_METRICS_REFETCH_MS } from "@/lib/constants";
import { systemApi } from "@/services/system";
import { useActivityStore } from "@/stores/activity-store";
import { useUiStore } from "@/stores/ui-store";
import { useQuery } from "@tanstack/react-query";
import type { HealthState } from "@/types/domain";
import { Moon, Sun } from "lucide-react";

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

  return <HealthBadge status={status} label="API" />;
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
  const pathname = usePathname();
  const router = useRouter();
  const queryClient = useQueryClient();
  const setCommandOpen = useUiStore((s) => s.setCommandOpen);
  const toggleActivity = useUiStore((s) => s.toggleActivity);
  const activityOpen = useUiStore((s) => s.activityOpen);
  const runningCount = useActivityStore(
    (s) => s.items.filter((item) => item.status === "running").length,
  );

  useKeyboardShortcuts();

  useEffect(() => {
    function onRefresh(event: KeyboardEvent) {
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      if (event.key.toLowerCase() !== "r") return;
      const target = event.target;
      if (
        target instanceof HTMLElement &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable)
      ) {
        return;
      }
      event.preventDefault();
      void queryClient.invalidateQueries();
      window.dispatchEvent(new CustomEvent("aip:refresh"));
    }
    window.addEventListener("keydown", onRefresh);
    return () => window.removeEventListener("keydown", onRefresh);
  }, [queryClient]);

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-2 border-b border-border bg-background/80 px-4 backdrop-blur">
      <Button
        variant="outline"
        size="sm"
        className="hidden min-w-48 justify-start gap-2 text-muted-foreground sm:inline-flex"
        onClick={() => setCommandOpen(true)}
        aria-label="Open command palette"
      >
        <Search className="size-3.5" />
        <span className="flex-1 text-left text-xs">Search…</span>
        <kbd className="rounded border border-border px-1.5 font-mono text-[10px]">
          ⌘K
        </kbd>
      </Button>

      <div className="ml-auto flex items-center gap-1.5">
        <Button
          size="icon"
          variant="ghost"
          aria-label="Upload"
          title="Upload (U)"
          onClick={() => router.push(ROUTES.upload)}
        >
          <Upload />
        </Button>
        <Button
          size="icon"
          variant="ghost"
          aria-label="Refresh"
          title="Refresh (R)"
          onClick={() => {
            void queryClient.invalidateQueries();
            window.dispatchEvent(new CustomEvent("aip:refresh"));
          }}
        >
          <RefreshCw />
        </Button>
        {pathname !== ROUTES.benchmark ? (
          <Button
            size="icon"
            variant="ghost"
            aria-label="Benchmark"
            title="Benchmark (G)"
            onClick={() => router.push(ROUTES.benchmark)}
            className="hidden md:inline-flex"
          >
            <Gauge />
          </Button>
        ) : null}
        <Button
          size="icon"
          variant={activityOpen ? "secondary" : "ghost"}
          aria-label="Activity"
          title="Activity (A)"
          className="relative"
          onClick={toggleActivity}
        >
          <Activity />
          {runningCount > 0 ? (
            <span className="absolute right-1.5 top-1.5 size-1.5 rounded-full bg-info" />
          ) : null}
        </Button>
        <SystemHealthIndicator />
        <ThemeToggle />
      </div>
    </header>
  );
}

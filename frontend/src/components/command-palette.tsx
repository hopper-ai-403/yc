"use client";

import {
  Activity,
  ClipboardCheck,
  FolderKanban,
  Gauge,
  LayoutDashboard,
  Search,
  Upload,
  Waves,
} from "lucide-react";
import { useRouter } from "next/navigation";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react";
import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";

import { Badge } from "@/components/ui/badge";
import { ROUTES } from "@/lib/constants";
import { cn } from "@/lib/utils";
import { listJobs } from "@/services/batch";
import { useActivityStore } from "@/stores/activity-store";
import { useUiStore } from "@/stores/ui-store";

interface CommandItem {
  id: string;
  label: string;
  hint?: string;
  group: string;
  href: string;
  icon: typeof Search;
  keywords?: string[];
}

const STATIC_COMMANDS: CommandItem[] = [
  {
    id: "nav-dashboard",
    label: "Dashboard",
    group: "Pages",
    href: ROUTES.dashboard,
    icon: LayoutDashboard,
    keywords: ["home", "overview"],
  },
  {
    id: "nav-upload",
    label: "Upload Studio",
    group: "Pages",
    href: ROUTES.upload,
    icon: Upload,
    keywords: ["zip", "files"],
    hint: "U",
  },
  {
    id: "nav-batches",
    label: "Batch Explorer",
    group: "Pages",
    href: ROUTES.batches,
    icon: FolderKanban,
    keywords: ["jobs"],
    hint: "B",
  },
  {
    id: "nav-benchmark",
    label: "Benchmark Dashboard",
    group: "Pages",
    href: ROUTES.benchmark,
    icon: Gauge,
    keywords: ["latency", "p95"],
    hint: "G",
  },
  {
    id: "nav-evaluation",
    label: "Evaluation Studio",
    group: "Pages",
    href: ROUTES.evaluation,
    icon: ClipboardCheck,
    keywords: ["accuracy", "ground truth"],
    hint: "E",
  },
  {
    id: "nav-system",
    label: "System",
    group: "Pages",
    href: ROUTES.system,
    icon: Activity,
    keywords: ["health", "workers"],
  },
];

function matches(item: CommandItem, query: string): boolean {
  if (!query) return true;
  const haystack = [item.label, item.group, ...(item.keywords ?? [])]
    .join(" ")
    .toLowerCase();
  return query
    .toLowerCase()
    .split(/\s+/)
    .every((token) => haystack.includes(token));
}

export function CommandPalette() {
  const open = useUiStore((s) => s.commandOpen);
  const setOpen = useUiStore((s) => s.setCommandOpen);
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const activityItems = useActivityStore((s) => s.items);

  const jobsQuery = useQuery({
    queryKey: ["command", "jobs"],
    queryFn: () => listJobs({ limit: 30 }),
    enabled: open,
    staleTime: 15_000,
  });

  const items = useMemo(() => {
    const batchItems: CommandItem[] =
      jobsQuery.data?.items.map((job) => ({
        id: `batch-${job.batch_id}`,
        label: `Batch ${job.batch_id.slice(0, 8)}`,
        hint: job.status,
        group: "Batches",
        href: ROUTES.batchDetail(job.batch_id),
        icon: FolderKanban,
        keywords: [job.batch_id, job.id, job.status],
      })) ?? [];

    const recentUploads: CommandItem[] = activityItems
      .filter((item) => item.kind === "upload" && item.href)
      .slice(0, 5)
      .map((item) => ({
        id: `activity-${item.id}`,
        label: item.title,
        hint: item.description,
        group: "Recent uploads",
        href: item.href!,
        icon: Upload,
        keywords: [item.description ?? ""],
      }));

    const predictionItems: CommandItem[] =
      jobsQuery.data?.items
        .filter((job) => job.status === "COMPLETED")
        .slice(0, 8)
        .map((job) => ({
          id: `pred-${job.batch_id}`,
          label: `Predictions · ${job.batch_id.slice(0, 8)}`,
          hint: `${job.processed_files} files`,
          group: "Predictions",
          href: ROUTES.batchDetail(job.batch_id),
          icon: Waves,
          keywords: [job.batch_id, "prediction"],
        })) ?? [];

    return [...STATIC_COMMANDS, ...recentUploads, ...batchItems, ...predictionItems].filter(
      (item) => matches(item, query),
    );
  }, [jobsQuery.data, activityItems, query]);

  useEffect(() => {
    if (!open) {
      setQuery("");
      setActive(0);
      return;
    }
    const timer = window.setTimeout(() => inputRef.current?.focus(), 10);
    return () => window.clearTimeout(timer);
  }, [open]);

  useEffect(() => {
    setActive(0);
  }, [query]);

  const run = useCallback(
    (item: CommandItem) => {
      setOpen(false);
      router.push(item.href);
    },
    [router, setOpen],
  );

  function onKeyDown(event: ReactKeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((value) => Math.min(value + 1, Math.max(items.length - 1, 0)));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((value) => Math.max(value - 1, 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      const item = items[active];
      if (item) run(item);
    }
  }

  const groups = useMemo(() => {
    const map = new Map<string, CommandItem[]>();
    for (const item of items) {
      const list = map.get(item.group) ?? [];
      list.push(item);
      map.set(item.group, list);
    }
    return [...map.entries()];
  }, [items]);

  let flatIndex = -1;

  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          className="fixed inset-0 z-50 flex items-start justify-center bg-background/70 px-4 pt-[12vh] backdrop-blur-sm"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.12 }}
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setOpen(false);
          }}
          role="dialog"
          aria-modal="true"
          aria-label="Command palette"
        >
          <motion.div
            initial={{ opacity: 0, y: -8, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.98 }}
            transition={{ duration: 0.15 }}
            className="w-full max-w-xl overflow-hidden rounded-xl border border-border bg-card shadow-2xl"
          >
            <div className="flex items-center gap-2 border-b border-border px-3">
              <Search className="size-4 text-muted-foreground" />
              <input
                ref={inputRef}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={onKeyDown}
                placeholder="Search batches, pages, predictions…"
                className="h-12 w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground"
                aria-label="Search"
              />
              <Badge variant="muted" className="font-mono text-[10px]">
                Esc
              </Badge>
            </div>
            <div className="max-h-80 overflow-y-auto p-2">
              {items.length === 0 ? (
                <p className="px-2 py-8 text-center text-xs text-muted-foreground">
                  No matches for “{query}”
                </p>
              ) : (
                groups.map(([group, groupItems]) => (
                  <div key={group} className="mb-2">
                    <p className="px-2 py-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                      {group}
                    </p>
                    <ul role="listbox" aria-label={group}>
                      {groupItems.map((item) => {
                        flatIndex += 1;
                        const index = flatIndex;
                        const Icon = item.icon;
                        const selected = index === active;
                        return (
                          <li key={item.id}>
                            <button
                              type="button"
                              role="option"
                              aria-selected={selected}
                              onMouseEnter={() => setActive(index)}
                              onClick={() => run(item)}
                              className={cn(
                                "flex w-full items-center gap-2.5 rounded-md px-2 py-2 text-left text-sm transition-colors",
                                selected
                                  ? "bg-accent text-accent-foreground"
                                  : "text-foreground hover:bg-accent/50",
                              )}
                            >
                              <Icon className="size-4 shrink-0 text-muted-foreground" />
                              <span className="min-w-0 flex-1 truncate">{item.label}</span>
                              {item.hint ? (
                                <span className="truncate font-mono text-[10px] text-muted-foreground">
                                  {item.hint}
                                </span>
                              ) : null}
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                ))
              )}
            </div>
            <div className="flex items-center justify-between border-t border-border px-3 py-2 text-[10px] text-muted-foreground">
              <span>↑↓ navigate · ↵ open</span>
              <span className="font-mono">Ctrl+K</span>
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

"use client";

import {
  Activity,
  FileAudio,
  FolderKanban,
  Gauge,
  LayoutDashboard,
  PanelLeftClose,
  PanelLeftOpen,
  Upload,
  Waves,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { APP_NAME, ROUTES } from "@/lib/constants";
import { cn } from "@/lib/utils";
import { useUiStore } from "@/stores/ui-store";

interface NavItem {
  href: string;
  label: string;
  icon: typeof LayoutDashboard;
  match?: (pathname: string) => boolean;
}

const NAV_ITEMS: NavItem[] = [
  { href: ROUTES.dashboard, label: "Dashboard", icon: LayoutDashboard },
  { href: ROUTES.upload, label: "Upload", icon: Upload },
  {
    href: ROUTES.batches,
    label: "Batches",
    icon: FolderKanban,
    match: (path) => path.startsWith("/batches"),
  },
  {
    href: ROUTES.batches,
    label: "Audio",
    icon: FileAudio,
    match: (path) => path.startsWith("/audio"),
  },
  { href: ROUTES.benchmark, label: "Benchmark", icon: Gauge },
  { href: ROUTES.system, label: "System", icon: Activity },
];

function isActive(item: NavItem, pathname: string): boolean {
  if (item.match) return item.match(pathname);
  if (item.href === ROUTES.dashboard) return pathname === ROUTES.dashboard;
  return pathname.startsWith(item.href);
}

export function Sidebar() {
  const pathname = usePathname();
  const collapsed = useUiStore((state) => state.sidebarCollapsed);
  const toggleSidebar = useUiStore((state) => state.toggleSidebar);

  return (
    <aside
      className={cn(
        "sticky top-0 flex h-screen shrink-0 flex-col border-r border-border bg-card/50 transition-[width] duration-200",
        collapsed ? "w-14" : "w-56",
      )}
    >
      <div
        className={cn(
          "flex h-14 items-center gap-2 border-b border-border px-3",
          collapsed && "justify-center px-0",
        )}
      >
        <div className="flex size-7 shrink-0 items-center justify-center rounded-md border border-border bg-muted">
          <Waves className="size-4 text-foreground" />
        </div>
        {!collapsed ? (
          <span className="truncate text-sm font-semibold tracking-tight">
            {APP_NAME}
          </span>
        ) : null}
      </div>

      <nav className="flex-1 space-y-0.5 overflow-y-auto p-2">
        {NAV_ITEMS.map((item) => {
          const active = isActive(item, pathname);
          const Icon = item.icon;
          return (
            <Link
              key={item.label}
              href={item.href}
              aria-current={active ? "page" : undefined}
              title={collapsed ? item.label : undefined}
              className={cn(
                "flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition-colors",
                active
                  ? "bg-accent font-medium text-accent-foreground"
                  : "text-muted-foreground hover:bg-accent/50 hover:text-foreground",
                collapsed && "justify-center px-0",
              )}
            >
              <Icon className="size-4 shrink-0" />
              {!collapsed ? item.label : null}
            </Link>
          );
        })}
      </nav>

      <Separator />
      <div className="p-2">
        <Button
          variant="ghost"
          size={collapsed ? "icon" : "sm"}
          className={cn(!collapsed && "w-full justify-start")}
          onClick={toggleSidebar}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <PanelLeftOpen /> : <PanelLeftClose />}
          {!collapsed ? <span>Collapse</span> : null}
        </Button>
      </div>
    </aside>
  );
}

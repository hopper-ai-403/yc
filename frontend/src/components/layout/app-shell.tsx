"use client";

import dynamic from "next/dynamic";
import type { ReactNode } from "react";

import { Sidebar } from "./sidebar";
import { TopNav } from "./top-nav";

const CommandPalette = dynamic(
  () =>
    import("@/components/command-palette").then((mod) => mod.CommandPalette),
  { ssr: false },
);
const ActivityDrawer = dynamic(
  () =>
    import("@/components/activity-drawer").then((mod) => mod.ActivityDrawer),
  { ssr: false },
);
const DetailDrawer = dynamic(
  () => import("@/components/detail-drawer").then((mod) => mod.DetailDrawer),
  { ssr: false },
);

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopNav />
        <main className="flex-1 animate-fade-in">{children}</main>
      </div>
      <CommandPalette />
      <ActivityDrawer />
      <DetailDrawer />
    </div>
  );
}

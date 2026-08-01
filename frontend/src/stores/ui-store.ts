"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

export type DrawerKind =
  | "prediction"
  | "metadata"
  | "batch"
  | "artifact"
  | null;

export interface DrawerPayload {
  kind: Exclude<DrawerKind, null>;
  id: string;
  title?: string;
  data?: Record<string, unknown>;
}

interface UiState {
  sidebarCollapsed: boolean;
  sidebarMobileOpen: boolean;
  commandOpen: boolean;
  activityOpen: boolean;
  drawer: DrawerPayload | null;
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  setSidebarMobileOpen: (open: boolean) => void;
  setCommandOpen: (open: boolean) => void;
  toggleCommand: () => void;
  setActivityOpen: (open: boolean) => void;
  toggleActivity: () => void;
  openDrawer: (payload: DrawerPayload) => void;
  closeDrawer: () => void;
}

/** UI-only client state. Server data lives exclusively in TanStack Query. */
export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      sidebarCollapsed: false,
      sidebarMobileOpen: false,
      commandOpen: false,
      activityOpen: false,
      drawer: null,
      toggleSidebar: () =>
        set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
      setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
      setSidebarMobileOpen: (open) => set({ sidebarMobileOpen: open }),
      setCommandOpen: (open) => set({ commandOpen: open }),
      toggleCommand: () => set((state) => ({ commandOpen: !state.commandOpen })),
      setActivityOpen: (open) => set({ activityOpen: open }),
      toggleActivity: () =>
        set((state) => ({ activityOpen: !state.activityOpen })),
      openDrawer: (payload) => set({ drawer: payload, activityOpen: false }),
      closeDrawer: () => set({ drawer: null }),
    }),
    {
      name: "aip-ui",
      partialize: (state) => ({ sidebarCollapsed: state.sidebarCollapsed }),
    },
  ),
);

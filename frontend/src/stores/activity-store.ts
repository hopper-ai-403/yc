"use client";

import { create } from "zustand";

export type ActivityKind =
  | "upload"
  | "job"
  | "prediction"
  | "export"
  | "error"
  | "system";

export type ActivityStatus =
  | "running"
  | "success"
  | "failed"
  | "queued"
  | "info";

export interface ActivityItem {
  id: string;
  kind: ActivityKind;
  status: ActivityStatus;
  title: string;
  description?: string;
  href?: string;
  progress?: number;
  createdAt: number;
  updatedAt: number;
  dismissible?: boolean;
}

interface ActivityState {
  items: ActivityItem[];
  push: (item: Omit<ActivityItem, "createdAt" | "updatedAt"> & { createdAt?: number }) => void;
  update: (id: string, patch: Partial<ActivityItem>) => void;
  remove: (id: string) => void;
  clear: () => void;
}

const MAX_ITEMS = 40;

export const useActivityStore = create<ActivityState>((set) => ({
  items: [],
  push: (item) =>
    set((state) => {
      const now = Date.now();
      const next: ActivityItem = {
        dismissible: true,
        ...item,
        createdAt: item.createdAt ?? now,
        updatedAt: now,
      };
      const without = state.items.filter((existing) => existing.id !== next.id);
      return {
        items: [next, ...without].slice(0, MAX_ITEMS),
      };
    }),
  update: (id, patch) =>
    set((state) => ({
      items: state.items.map((item) =>
        item.id === id ? { ...item, ...patch, updatedAt: Date.now() } : item,
      ),
    })),
  remove: (id) =>
    set((state) => ({
      items: state.items.filter((item) => item.id !== id),
    })),
  clear: () => set({ items: [] }),
}));

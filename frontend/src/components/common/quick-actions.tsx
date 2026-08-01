"use client";

import type { LucideIcon } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface QuickAction {
  id: string;
  label: string;
  icon?: LucideIcon;
  href?: string;
  onClick?: () => void;
  variant?: "default" | "outline" | "ghost" | "secondary";
  shortcut?: string;
  disabled?: boolean;
}

interface QuickActionsProps {
  actions: QuickAction[];
  className?: string;
}

export function QuickActions({ actions, className }: QuickActionsProps) {
  return (
    <div className={cn("flex flex-wrap items-center gap-1.5", className)}>
      {actions.map((action) => {
        const Icon = action.icon;
        const content = (
          <>
            {Icon ? <Icon /> : null}
            <span>{action.label}</span>
            {action.shortcut ? (
              <kbd className="ml-0.5 hidden rounded border border-border px-1 font-mono text-[10px] text-muted-foreground sm:inline">
                {action.shortcut}
              </kbd>
            ) : null}
          </>
        );

        if (action.href) {
          return (
            <Link key={action.id} href={action.href}>
              <Button
                size="sm"
                variant={action.variant ?? "outline"}
                disabled={action.disabled}
              >
                {content}
              </Button>
            </Link>
          );
        }

        return (
          <Button
            key={action.id}
            size="sm"
            variant={action.variant ?? "outline"}
            disabled={action.disabled}
            onClick={action.onClick}
          >
            {content}
          </Button>
        );
      })}
    </div>
  );
}

export function ShortcutHint({ children }: { children: ReactNode }) {
  return (
    <span className="hidden items-center gap-1 text-[10px] text-muted-foreground md:inline-flex">
      {children}
    </span>
  );
}

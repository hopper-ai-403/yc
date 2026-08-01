"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { ROUTES } from "@/lib/constants";
import { useUiStore } from "@/stores/ui-store";

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  return (
    tag === "INPUT" ||
    tag === "TEXTAREA" ||
    tag === "SELECT" ||
    target.isContentEditable
  );
}

/** Global keyboard shortcuts. Esc closes overlays; letter shortcuts skip typing targets. */
export function useKeyboardShortcuts() {
  const router = useRouter();
  const setCommandOpen = useUiStore((s) => s.setCommandOpen);
  const toggleCommand = useUiStore((s) => s.toggleCommand);
  const setActivityOpen = useUiStore((s) => s.setActivityOpen);
  const closeDrawer = useUiStore((s) => s.closeDrawer);
  const commandOpen = useUiStore((s) => s.commandOpen);
  const activityOpen = useUiStore((s) => s.activityOpen);
  const drawer = useUiStore((s) => s.drawer);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const meta = event.metaKey || event.ctrlKey;

      if (meta && event.key.toLowerCase() === "k") {
        event.preventDefault();
        toggleCommand();
        return;
      }

      if (event.key === "Escape") {
        if (commandOpen) {
          setCommandOpen(false);
          return;
        }
        if (drawer) {
          closeDrawer();
          return;
        }
        if (activityOpen) {
          setActivityOpen(false);
        }
        return;
      }

      if (meta || event.altKey || isTypingTarget(event.target)) return;

      switch (event.key.toLowerCase()) {
        case "u":
          event.preventDefault();
          router.push(ROUTES.upload);
          break;
        case "b":
          event.preventDefault();
          router.push(ROUTES.batches);
          break;
        case "e":
          event.preventDefault();
          router.push(ROUTES.evaluation);
          break;
        case "g":
          event.preventDefault();
          router.push(ROUTES.benchmark);
          break;
        case "a":
          event.preventDefault();
          setActivityOpen(true);
          break;
        case "/":
          event.preventDefault();
          setCommandOpen(true);
          break;
        default:
          break;
      }
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [
    router,
    toggleCommand,
    setCommandOpen,
    setActivityOpen,
    closeDrawer,
    commandOpen,
    activityOpen,
    drawer,
  ]);
}

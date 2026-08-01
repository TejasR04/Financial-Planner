"use client";

import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";

const FOCUSABLE = [
  "button:not([disabled])",
  "[href]",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

export function DialogShell({
  children,
  onClose,
  closeDisabled = false,
  ariaLabel,
  ariaLabelledBy,
  overlayClassName,
  panelClassName,
}: {
  children: React.ReactNode;
  onClose: () => void;
  closeDisabled?: boolean;
  ariaLabel?: string;
  ariaLabelledBy?: string;
  overlayClassName?: string;
  panelClassName?: string;
}) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const previouslyFocused = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;
    const panel = panelRef.current;
    const frame = requestAnimationFrame(() => {
      const firstFocusable = panel?.querySelector<HTMLElement>(FOCUSABLE);
      (firstFocusable ?? panel)?.focus();
    });

    return () => {
      cancelAnimationFrame(frame);
      previouslyFocused?.focus();
    };
  }, []);

  return (
    <div
      className={cn(
        "fixed inset-0 z-50 flex items-center justify-center bg-foreground/20 p-4 backdrop-blur-sm",
        overlayClassName,
      )}
      onMouseDown={(event) => {
        if (!closeDisabled && event.target === event.currentTarget) onClose();
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={ariaLabel}
        aria-labelledby={ariaLabelledBy}
        tabIndex={-1}
        className={cn(
          "w-full rounded-xl border border-border bg-popover shadow-2xl outline-none",
          panelClassName,
        )}
        onKeyDown={(event) => {
          if (event.key === "Escape" && !closeDisabled) {
            event.preventDefault();
            onClose();
            return;
          }
          if (event.key !== "Tab") return;
          const focusable = Array.from(panelRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? []);
          if (focusable.length === 0) {
            event.preventDefault();
            panelRef.current?.focus();
            return;
          }
          const first = focusable[0];
          const last = focusable[focusable.length - 1];
          if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
          } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
          }
        }}
      >
        {children}
      </div>
    </div>
  );
}

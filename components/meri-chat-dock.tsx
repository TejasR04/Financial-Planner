"use client";

import { Grip, MessageCircle } from "lucide-react";
import { useEffect, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import { GeminiAssistant } from "@/components/gemini-assistant";
import { useMeriChat } from "@/components/meri-chat-context";
import { useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/utils";

type Position = "left" | "center" | "right";

export function MeriChatDock() {
  const { isDemo } = useAuth();
  const { popupOpen, setPopupOpen } = useMeriChat();
  const [position, setPosition] = useState<Position>("right");
  const [size, setSize] = useState({ width: 420, height: 680 });
  const panelRef = useRef<HTMLDivElement>(null);
  const launcherRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!popupOpen) return;
    panelRef.current?.querySelector("textarea")?.focus();
    const onKeyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") {
        setPopupOpen(false);
        requestAnimationFrame(() => launcherRef.current?.focus());
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [popupOpen, setPopupOpen]);

  function cyclePosition() {
    setPosition((current) => current === "right" ? "center" : current === "center" ? "left" : "right");
  }

  function startMove(event: PointerEvent<HTMLDivElement>) {
    if (event.target instanceof Element && event.target.closest("button, input, textarea")) return;
    const panel = panelRef.current;
    if (!panel) return;
    const pointerId = event.pointerId;
    const startX = event.clientX;
    const startY = event.clientY;
    let active = event.pointerType !== "touch";
    let moved = false;
    const hold = event.pointerType === "touch" ? window.setTimeout(() => { active = true; }, 320) : null;
    const cleanup = () => {
      if (hold !== null) window.clearTimeout(hold);
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", finish);
      window.removeEventListener("pointercancel", cancel);
      panel.style.translate = "";
    };
    const move = (next: globalThis.PointerEvent) => {
      if (next.pointerId !== pointerId) return;
      const dx = next.clientX - startX;
      const dy = next.clientY - startY;
      if (!active) {
        if (Math.hypot(dx, dy) > 8 && hold !== null) window.clearTimeout(hold);
        return;
      }
      moved = moved || Math.hypot(dx, dy) > 8;
      panel.style.translate = `${dx}px ${dy}px`;
    };
    const finish = (next: globalThis.PointerEvent) => {
      if (next.pointerId !== pointerId) return;
      cleanup();
      if (!active || !moved) return;
      const fraction = next.clientX / window.innerWidth;
      setPosition(fraction < 1 / 3 ? "left" : fraction > 2 / 3 ? "right" : "center");
    };
    const cancel = (next: globalThis.PointerEvent) => {
      if (next.pointerId === pointerId) cleanup();
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", finish);
    window.addEventListener("pointercancel", cancel);
  }

  function startResize(event: PointerEvent<HTMLDivElement>) {
    event.stopPropagation();
    event.preventDefault();
    const panel = panelRef.current;
    if (!panel) return;
    const pointerId = event.pointerId;
    const startX = event.clientX;
    const startY = event.clientY;
    const bounds = panel.getBoundingClientRect();
    const cleanup = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", finish);
      window.removeEventListener("pointercancel", finish);
    };
    const move = (next: globalThis.PointerEvent) => {
      if (next.pointerId !== pointerId) return;
      const direction = position === "right" ? -1 : 1;
      const width = Math.max(Math.min(320, window.innerWidth - 32),
        Math.min(window.innerWidth - 32, bounds.width + direction * (next.clientX - startX)));
      const height = Math.max(Math.min(360, window.innerHeight - 96),
        Math.min(window.innerHeight - 96, bounds.height - (next.clientY - startY)));
      setSize({ width: Math.round(width), height: Math.round(height) });
    };
    const finish = (next: globalThis.PointerEvent) => {
      if (next.pointerId === pointerId) cleanup();
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", finish);
    window.addEventListener("pointercancel", finish);
  }

  function resizeWithKeyboard(event: KeyboardEvent<HTMLDivElement>) {
    const changes: Record<string, [number, number]> = {
      ArrowLeft: [-32, 0], ArrowRight: [32, 0], ArrowUp: [0, 32], ArrowDown: [0, -32],
    };
    const change = changes[event.key];
    if (!change) return;
    event.preventDefault();
    setSize((current) => ({
      width: Math.max(Math.min(320, window.innerWidth - 32), Math.min(window.innerWidth - 32, current.width + change[0])),
      height: Math.max(Math.min(360, window.innerHeight - 96), Math.min(window.innerHeight - 96, current.height + change[1])),
    }));
  }

  if (isDemo) return null;
  return (
    <div className="pointer-events-none fixed inset-0 z-40">
      {popupOpen && (
        <div ref={panelRef} role="dialog" aria-label="Meri chat" data-position={position}
          style={{ width: `min(${size.width}px, calc(100vw - 2rem))`, height: `min(${size.height}px, calc(100dvh - 6rem))` }}
          className={cn("pointer-events-auto absolute bottom-4 flex flex-col rounded-xl bg-card shadow-2xl sm:bottom-6",
            position === "left" ? "left-4 sm:left-6" : position === "center" ? "left-1/2 -translate-x-1/2" : "right-4 sm:right-6")}
        >
          <GeminiAssistant popup position={position} onMoveStart={startMove} onCyclePosition={cyclePosition} />
          <div role="button" tabIndex={0} aria-label="Resize Meri chat" title="Drag to resize; arrow keys also work"
            onPointerDown={startResize} onKeyDown={resizeWithKeyboard}
            className={cn("absolute bottom-0 flex size-8 touch-none items-center justify-center rounded-md bg-card/90 text-muted-foreground cursor-nwse-resize focus-visible:outline-2 focus-visible:outline-primary",
              position === "right" ? "left-0" : "right-0")}>
            <Grip className="size-4" />
          </div>
        </div>
      )}
      {!popupOpen && (
        <button ref={launcherRef} type="button" aria-label="Open Meri chat" onClick={() => setPopupOpen(true)}
          className="pointer-events-auto absolute bottom-4 right-4 flex items-center gap-2 rounded-full bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground shadow-lg hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary sm:bottom-6 sm:right-6">
          <MessageCircle className="size-5" /> Meri
        </button>
      )}
    </div>
  );
}

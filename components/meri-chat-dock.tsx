"use client";

import { MessageCircle } from "lucide-react";
import { useEffect, useRef } from "react";
import { GeminiAssistant } from "@/components/gemini-assistant";
import { useMeriChat } from "@/components/meri-chat-context";
import { useAuth } from "@/lib/auth-context";

export function MeriChatDock() {
  const { isDemo } = useAuth();
  const { popupOpen, setPopupOpen } = useMeriChat();
  const panelRef = useRef<HTMLDivElement>(null);
  const launcherRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!popupOpen) return;
    panelRef.current?.querySelector("textarea")?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setPopupOpen(false);
        requestAnimationFrame(() => launcherRef.current?.focus());
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [popupOpen, setPopupOpen]);
  if (isDemo) return null;
  return (
    <div className="fixed bottom-4 right-4 z-40 flex flex-col items-end gap-2 sm:bottom-6 sm:right-6">
      {popupOpen && (
        <div ref={panelRef} role="dialog" aria-label="Meri chat" className="flex h-[min(680px,calc(100dvh-6rem))] w-[min(420px,calc(100vw-2rem))] flex-col overflow-hidden rounded-xl bg-card shadow-2xl">
          <GeminiAssistant popup />
        </div>
      )}
      {!popupOpen && (
        <button ref={launcherRef} type="button" aria-label="Open Meri chat" onClick={() => setPopupOpen(true)}
          className="flex items-center gap-2 rounded-full bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground shadow-lg hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary">
          <MessageCircle className="size-5" /> Meri
        </button>
      )}
    </div>
  );
}

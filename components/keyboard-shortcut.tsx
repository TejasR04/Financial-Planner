"use client";

import { useEffect, useState } from "react";

function isMac() {
  return /Mac|iPhone|iPad|iPod/i.test(navigator.userAgent);
}

export function KeyboardShortcut({ keyName, withAlt = false }: { keyName: string; withAlt?: boolean }) {
  const [mac, setMac] = useState(false);
  useEffect(() => setMac(isMac()), []);
  return <span className="flex items-center gap-0.5 text-[10px] text-muted-foreground/60" aria-label={`${mac ? "Command" : "Control"}${withAlt ? mac ? " Option" : " Alt" : ""} ${keyName}`}><kbd className="font-sans">{mac ? "⌘" : "Ctrl"}</kbd>{withAlt && <kbd className="font-sans">{mac ? "⌥" : "Alt"}</kbd>}<kbd className="font-mono">{keyName}</kbd></span>;
}

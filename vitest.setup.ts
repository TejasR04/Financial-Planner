import "@testing-library/jest-dom/vitest";

globalThis.requestAnimationFrame = (callback: FrameRequestCallback) =>
  window.setTimeout(() => callback(performance.now()), 0);
globalThis.cancelAnimationFrame = (handle: number) => window.clearTimeout(handle);

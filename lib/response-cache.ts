/** Tab-memory only: never persist financial responses to browser storage. */
export const RESPONSE_CACHE_TTL_MS = 2 * 60 * 1000;

export class ResponseCache {
  private entries = new Map<string, { expires: number; value: unknown }>();
  private generation = 0;

  clear() {
    this.generation += 1;
    this.entries.clear();
  }

  async load<T>(key: string, loader: () => Promise<T>, signal?: AbortSignal | null): Promise<T> {
    signal?.throwIfAborted();
    const cached = this.entries.get(key);
    if (cached && cached.expires > Date.now()) return structuredClone(cached.value) as T;
    this.entries.delete(key);
    const generation = this.generation;
    // Each consumer owns its request, so unmounting one never aborts another.
    const value = await loader();
    signal?.throwIfAborted();
    if (generation === this.generation) {
      if (this.entries.size >= 100) this.entries.delete(this.entries.keys().next().value!);
      this.entries.set(key, { expires: Date.now() + RESPONSE_CACHE_TTL_MS, value: structuredClone(value) });
    }
    return value;
  }
}

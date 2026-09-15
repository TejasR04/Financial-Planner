/** Keep partial failures visible and avoid flooding the server with requests. */
export async function applyToTransactions(ids: string[], action: (id: string) => Promise<unknown>) {
  const succeeded: string[] = [];
  const failed: string[] = [];
  const errors: string[] = [];
  for (let index = 0; index < ids.length; index += 5) {
    const batch = ids.slice(index, index + 5);
    const results = await Promise.allSettled(batch.map(action));
    results.forEach((result, position) => {
      if (result.status === "fulfilled") succeeded.push(batch[position]);
      else {
        failed.push(batch[position]);
        errors.push(result.reason instanceof Error ? result.reason.message : "Could not update transaction.");
      }
    });
  }
  return { succeeded, failed, errors };
}

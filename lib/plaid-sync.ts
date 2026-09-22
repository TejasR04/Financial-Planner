import { api } from "@/lib/api-client";

let activeDataRefresh: ReturnType<typeof api.sync.all> | null = null;

/** Deduplicate full financial-data refreshes across the top bar and Accounts page. */
export function requestDataRefresh() {
  if (activeDataRefresh === null) {
    activeDataRefresh = api.sync.all().finally(() => {
      activeDataRefresh = null;
    });
  }
  return activeDataRefresh;
}

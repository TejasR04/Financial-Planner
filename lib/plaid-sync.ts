import { api } from "@/lib/api-client";

let activePlaidRefresh: ReturnType<typeof api.plaid.refresh> | null = null;

/** Deduplicate full Plaid refreshes across the top bar and Accounts page. */
export function requestPlaidRefresh() {
  if (activePlaidRefresh === null) {
    activePlaidRefresh = api.plaid.refresh().finally(() => {
      activePlaidRefresh = null;
    });
  }
  return activePlaidRefresh;
}

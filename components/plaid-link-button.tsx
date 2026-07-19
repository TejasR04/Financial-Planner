"use client";

import { useCallback, useEffect, useState } from "react";
import { usePlaidLink } from "react-plaid-link";
import { Loader2, Plus } from "lucide-react";

import { Button, type buttonVariants } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api-client";
import { useDataRefresh } from "@/lib/data-provider";
import type { VariantProps } from "class-variance-authority";

type Status = "idle" | "fetching_token" | "linking" | "error";

type Props = {
  label?: string;
  className?: string;
  onLinked?: () => void;
} & VariantProps<typeof buttonVariants>;

/**
 * Drop-in replacement for the old no-op "Link account" button.
 *
 * Security note: this component only ever handles two short-lived,
 * single-purpose values — a `link_token` (scoped to this user, expires in
 * minutes, can't read any data on its own) and a one-time `public_token`
 * (single-use, expires in ~30 min). The actual Plaid `access_token` is
 * created and stored server-side and never sent to the browser.
 */
export function PlaidLinkButton({ label = "Link account", className, onLinked, variant, size }: Props) {
  const [linkToken, setLinkToken] = useState<string | null>(null);
  const [status, setStatus] = useState<Status>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const refresh = useDataRefresh();

  const onSuccess = useCallback(
    async (publicToken: string) => {
      setStatus("linking");
      setErrorMessage(null);
      try {
        await api.plaid.exchangePublicToken(publicToken);
        refresh();
        onLinked?.();
        setStatus("idle");
      } catch (err) {
        setErrorMessage(
          err instanceof ApiError ? err.message : "Couldn't finish linking that account. Try again.",
        );
        setStatus("error");
      } finally {
        setLinkToken(null);
      }
    },
    [refresh, onLinked],
  );

  const onExit = useCallback(() => {
    setLinkToken(null);
    setStatus((current) => (current === "linking" ? current : "idle"));
  }, []);

  const { open, ready } = usePlaidLink({
    token: linkToken ?? "",
    onSuccess,
    onExit,
  });

  // Plaid Link needs a render cycle after the token is set before `ready`
  // flips true; open it as soon as it does rather than making the user
  // click twice.
  useEffect(() => {
    if (linkToken && ready) {
      open();
    }
  }, [linkToken, ready, open]);

  const handleClick = async () => {
    setErrorMessage(null);
    setStatus("fetching_token");
    try {
      const { link_token } = await api.plaid.createLinkToken();
      setLinkToken(link_token);
      setStatus("idle");
    } catch (err) {
      setErrorMessage(
        err instanceof ApiError ? err.message : "Couldn't start account linking. Try again.",
      );
      setStatus("error");
    }
  };

  const busy = status === "fetching_token" || status === "linking";

  return (
    <div className="inline-flex flex-col items-start gap-1">
      <Button variant={variant} size={size} className={className} onClick={handleClick} disabled={busy}>
        {busy ? <Loader2 className="animate-spin" /> : <Plus />}
        {label}
      </Button>
      {errorMessage && <p className="max-w-64 text-xs text-destructive">{errorMessage}</p>}
    </div>
  );
}

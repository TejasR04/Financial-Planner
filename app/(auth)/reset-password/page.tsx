"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api-client";

const inputClass =
  "h-9 w-full rounded-md border border-border bg-background px-3 text-[13px] text-foreground outline-none transition-colors placeholder:text-muted-foreground focus:border-ring focus:ring-3 focus:ring-ring/20";

export default function ResetPasswordPage() {
  const [token, setToken] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [complete, setComplete] = useState(false);

  useEffect(() => {
    setToken(new URLSearchParams(window.location.search).get("token") ?? "");
  }, []);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    if (!token) {
      setError("This password-reset link is invalid or has expired.");
      return;
    }
    if (password !== confirmation) {
      setError("Passwords do not match.");
      return;
    }
    setSubmitting(true);
    try {
      await api.auth.confirmPasswordReset(token, password);
      setComplete(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't reset your password.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 text-center">
          <p className="text-lg font-semibold tracking-tight text-foreground">Meridian</p>
          <p className="mt-1 text-[13px] text-muted-foreground">Choose a new password</p>
        </div>
        <form onSubmit={handleSubmit} className="flex flex-col gap-3.5 rounded-lg border border-border bg-card p-5">
          {complete ? (
            <p className="text-[13px] leading-relaxed text-muted-foreground" role="status">
              Your password has been reset. You can now sign in with it.
            </p>
          ) : (
            <>
              <div>
                <label htmlFor="password" className="text-[13px] font-medium text-foreground">New password</label>
                <input
                  id="password"
                  type="password"
                  required
                  minLength={8}
                  autoComplete="new-password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  className={`${inputClass} mt-1.5`}
                />
              </div>
              <div>
                <label htmlFor="confirmation" className="text-[13px] font-medium text-foreground">Confirm new password</label>
                <input
                  id="confirmation"
                  type="password"
                  required
                  minLength={8}
                  autoComplete="new-password"
                  value={confirmation}
                  onChange={(event) => setConfirmation(event.target.value)}
                  className={`${inputClass} mt-1.5`}
                />
              </div>
              {error && <p className="text-[12px] text-destructive" role="alert">{error}</p>}
              <Button type="submit" className="w-full" disabled={submitting}>
                {submitting ? "Resetting…" : "Reset password"}
              </Button>
            </>
          )}
        </form>
        <p className="mt-4 text-center text-[13px] text-muted-foreground">
          <Link href="/login" className="font-medium text-primary hover:underline">Back to sign in</Link>
        </p>
      </div>
    </div>
  );
}

"use client";

import { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";

const inputClass =
  "h-9 w-full rounded-md border border-border bg-background px-3 text-[13px] text-foreground outline-none transition-colors placeholder:text-muted-foreground focus:border-ring focus:ring-3 focus:ring-ring/20";

export default function RegisterPage() {
  const { register } = useAuth();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await register(email, password, fullName);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create account.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 text-center">
          <p className="text-lg font-semibold tracking-tight text-foreground">
            Meridian
          </p>
          <p className="mt-1 text-[13px] text-muted-foreground">
            Create your financial planning account
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="flex flex-col gap-3.5 rounded-lg border border-border bg-card p-5"
        >
          <div>
            <label htmlFor="fullName" className="text-[13px] font-medium text-foreground">
              Full name
            </label>
            <input
              id="fullName"
              type="text"
              required
              autoComplete="name"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className={`${inputClass} mt-1.5`}
              placeholder="Jane Doe"
            />
          </div>
          <div>
            <label htmlFor="email" className="text-[13px] font-medium text-foreground">
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={`${inputClass} mt-1.5`}
              placeholder="you@example.com"
            />
          </div>
          <div>
            <label htmlFor="password" className="text-[13px] font-medium text-foreground">
              Password
            </label>
            <input
              id="password"
              type="password"
              required
              autoComplete="new-password"
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={`${inputClass} mt-1.5`}
              placeholder="••••••••"
            />
          </div>

          {error && (
            <p className="text-[12px] text-destructive" role="alert">
              {error}
            </p>
          )}

          <Button type="submit" className="mt-1 w-full" disabled={submitting}>
            {submitting ? "Creating account…" : "Create account"}
          </Button>
        </form>

        <p className="mt-4 text-center text-[13px] text-muted-foreground">
          Already have an account?{" "}
          <Link href="/login" className="font-medium text-primary hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}

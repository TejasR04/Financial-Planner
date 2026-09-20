import Link from "next/link";

export default function RegisterPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 text-center">
          <p className="text-lg font-semibold tracking-tight text-foreground">
            Meridian
          </p>
          <p className="mt-1 text-[13px] text-muted-foreground">
            Registration is closed
          </p>
        </div>

        <div className="rounded-lg border border-border bg-card p-5 text-center">
          <p className="text-[13px] text-muted-foreground">
            New accounts are not being accepted.
          </p>
        </div>

        <p className="mt-4 text-center text-[13px] text-muted-foreground">
          <Link href="/login" className="font-medium text-primary hover:underline">
            Return to sign in
          </Link>
        </p>
      </div>
    </div>
  );
}

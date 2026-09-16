import { cn } from "@/lib/utils";

export function PageContainer({
  className,
  ...props
}: React.ComponentProps<"div">) {
  return (
    <div
      className={cn("mx-auto w-full min-w-0 max-w-[1360px] px-3 py-4 sm:px-5 sm:py-5", className)}
      {...props}
    />
  );
}

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className="mb-5 flex flex-col items-start justify-between gap-4 sm:flex-row sm:flex-wrap sm:items-end">
      <div className="min-w-0">
        <h1 className="text-xl font-semibold tracking-tight text-foreground text-balance">
          {title}
        </h1>
        {description ? (
          <p className="mt-1 text-[13px] text-muted-foreground text-pretty">
            {description}
          </p>
        ) : null}
      </div>
      {actions ? (
        <div className="flex max-w-full flex-wrap items-center gap-2">{actions}</div>
      ) : null}
    </div>
  );
}

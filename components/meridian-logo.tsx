import type { HTMLAttributes, SVGProps } from "react";
import { cn } from "@/lib/utils";

/** A geometric M, growth path, and meridian ring in one mark. */
export function MeridianMark({
  className,
  accentClassName = "fill-brand",
  ...props
}: SVGProps<SVGSVGElement> & { accentClassName?: string }) {
  return (
    <svg
      viewBox="0 0 32 32"
      fill="none"
      role="img"
      aria-label="Meridian"
      className={cn("h-8 w-8", className)}
      {...props}
    >
      <circle
        cx="16"
        cy="16"
        r="13.5"
        className="stroke-current opacity-15"
        strokeWidth="1.5"
      />
      <path
        d="M6 22.5 L11.5 11 L16 17.5 L20.5 11 L26 22.5"
        className="stroke-current"
        strokeWidth="2.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="26" cy="22.5" r="2.75" className={accentClassName} />
    </svg>
  );
}

export function MeridianWordmark({ className, ...props }: HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn(
        "font-sans text-2xl font-semibold tracking-tight text-foreground",
        className,
      )}
      {...props}
    >
      Meridian
    </span>
  );
}

type MeridianLogoProps = {
  variant?: "lockup" | "mark";
  className?: string;
  markClassName?: string;
  wordmarkClassName?: string;
};

export function MeridianLogo({
  variant = "lockup",
  className,
  markClassName,
  wordmarkClassName,
}: MeridianLogoProps) {
  return (
    <span className={cn("inline-flex items-center gap-2.5 text-foreground", className)}>
      <MeridianMark className={cn("h-8 w-8", markClassName)} />
      {variant === "lockup" && <MeridianWordmark className={wordmarkClassName} />}
    </span>
  );
}

export function MeridianAppIcon({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "flex aspect-square h-16 w-16 items-center justify-center rounded-[22%] bg-brand text-brand-foreground shadow-sm",
        className,
      )}
      {...props}
    >
      <MeridianMark className="h-3/5 w-3/5" accentClassName="fill-current" />
    </div>
  );
}

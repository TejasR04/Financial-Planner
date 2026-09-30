import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Budget — Meridian",
};

export default function BudgetLayout({ children }: { children: React.ReactNode }) {
  return children;
}

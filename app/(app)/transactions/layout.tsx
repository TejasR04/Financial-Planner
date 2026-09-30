import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Transactions — Meridian",
};

export default function TransactionsLayout({ children }: { children: React.ReactNode }) {
  return children;
}

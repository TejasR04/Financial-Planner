import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Investments — Meridian",
};

export default function InvestmentsLayout({ children }: { children: React.ReactNode }) {
  return children;
}

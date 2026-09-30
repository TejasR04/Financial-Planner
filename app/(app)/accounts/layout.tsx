import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Accounts — Meridian",
};

export default function AccountsLayout({ children }: { children: React.ReactNode }) {
  return children;
}

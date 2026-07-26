import {
  LayoutDashboard,
  Wallet,
  ReceiptText,
  TrendingUp,
  Landmark,
  CircleDollarSign,
  Sparkles,
  Settings,
  type LucideIcon,
} from "lucide-react";

export type NavItem = {
  label: string;
  href: string;
  icon: LucideIcon;
};

export type NavGroup = {
  label: string;
  items: NavItem[];
};

export const navGroups: NavGroup[] = [
  {
    label: "Workspace",
    items: [
      { label: "Overview", href: "/", icon: LayoutDashboard },
      { label: "Accounts", href: "/accounts", icon: Wallet },
      { label: "Transactions", href: "/transactions", icon: ReceiptText },
      { label: "Budget", href: "/budget", icon: CircleDollarSign },
      { label: "Investments", href: "/investments", icon: Landmark },
      {
        label: "Projections",
        href: "/projections",
        icon: TrendingUp,
      },
      { label: "Insights", href: "/insights", icon: Sparkles },
    ],
  },
  {
    label: "Configuration",
    items: [
      { label: "Settings", href: "/settings", icon: Settings },
    ],
  },
];

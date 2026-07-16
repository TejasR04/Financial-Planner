import {
  LayoutDashboard,
  Wallet,
  TrendingUp,
  Sparkles,
  Settings,
  type LucideIcon,
} from "lucide-react";

export type NavItem = {
  label: string;
  href: string;
  icon: LucideIcon;
  shortcut?: string;
};

export type NavGroup = {
  label: string;
  items: NavItem[];
};

export const navGroups: NavGroup[] = [
  {
    label: "Workspace",
    items: [
      { label: "Overview", href: "/", icon: LayoutDashboard, shortcut: "G O" },
      { label: "Accounts", href: "/accounts", icon: Wallet, shortcut: "G A" },
      {
        label: "Projections",
        href: "/projections",
        icon: TrendingUp,
        shortcut: "G P",
      },
      { label: "Insights", href: "/insights", icon: Sparkles, shortcut: "G I" },
    ],
  },
  {
    label: "Configuration",
    items: [
      { label: "Settings", href: "/settings", icon: Settings, shortcut: "G S" },
    ],
  },
];

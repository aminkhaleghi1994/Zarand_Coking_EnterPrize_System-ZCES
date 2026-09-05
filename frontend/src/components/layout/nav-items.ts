import {
  Banknote,
  ChartColumnBig,
  ClipboardList,
  LayoutDashboard,
  MonitorSmartphone,
  Settings,
  ShieldCheck,
  Users,
  Warehouse,
  type LucideIcon,
} from "lucide-react";

export type NavItem = {
  key: string;
  icon: LucideIcon;
  href?: string;
  phase?: number;
  /** Settings feature flag gating this item (flags.* key; fail-open). */
  flagKey?: string;
};

export type NavGroup = {
  key: string;
  items: NavItem[];
};

export const NAV_GROUPS: NavGroup[] = [
  {
    key: "operations",
    items: [
      { key: "dashboard", icon: LayoutDashboard, href: "/" },
      { key: "employees", icon: Users, href: "/employees" },
      { key: "warehouse", icon: Warehouse, href: "/warehouse" },
      { key: "requests", icon: ClipboardList, href: "/requests" },
      { key: "assets", icon: MonitorSmartphone, href: "/assets", flagKey: "flags.asset_module_enabled" },
      { key: "loans", icon: Banknote, href: "/loans", flagKey: "flags.loan_module_enabled" },
    ],
  },
  {
    key: "system",
    items: [
      { key: "admin", icon: ShieldCheck, href: "/admin" },
      { key: "reports", icon: ChartColumnBig, href: "/reports" },
      { key: "settings", icon: Settings, href: "/settings" },
    ],
  },
];

import {
  Banknote,
  ChartColumnBig,
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
      { key: "employees", icon: Users, phase: 3 },
      { key: "warehouse", icon: Warehouse, phase: 4 },
      { key: "assets", icon: MonitorSmartphone, phase: 6 },
      { key: "loans", icon: Banknote, phase: 7 },
    ],
  },
  {
    key: "system",
    items: [
      { key: "admin", icon: ShieldCheck, href: "/admin" },
      { key: "reports", icon: ChartColumnBig, phase: 9 },
      { key: "settings", icon: Settings, phase: 9 },
    ],
  },
];

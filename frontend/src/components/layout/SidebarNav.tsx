"use client";

import { useTranslations } from "next-intl";
import { usePathname } from "next/navigation";

import { Link } from "@/i18n/navigation";
import { cn } from "@/lib/utils";

import { NAV_GROUPS } from "./nav-items";

export function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const t = useTranslations("nav");
  const pathname = usePathname();

  return (
    <nav aria-label={t("menu")} className="grid gap-6">
      {NAV_GROUPS.map((group) => (
        <div key={group.key} className="grid gap-1">
          <p className="px-3 pb-1 text-xs font-bold uppercase tracking-widest text-graphite">
            {t(`groups.${group.key}`)}
          </p>
          {group.items.map((item) => {
            const Icon = item.icon;
            const active = item.href !== undefined && pathname === item.href;

            if (item.href) {
              return (
                <Link
                  key={item.key}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  onClick={onNavigate}
                  className={cn(
                    "flex h-11 items-center gap-3 rounded-md px-3 text-sm outline-none transition-colors duration-200 focus-visible:ring-2 focus-visible:ring-ring/50",
                    active
                      ? "bg-brand-soft font-bold text-brand-deep"
                      : "text-charcoal hover:bg-cloud hover:text-ink",
                  )}
                >
                  <Icon aria-hidden className="size-5 shrink-0" />
                  <span className="truncate">{t(item.key)}</span>
                </Link>
              );
            }

            return (
              <span
                key={item.key}
                aria-disabled="true"
                title={t("comingSoon")}
                className="flex h-11 items-center gap-3 rounded-md px-3 text-sm text-ink/40 select-none"
              >
                <Icon aria-hidden className="size-5 shrink-0" />
                <span className="truncate">{t(item.key)}</span>
                <span className="ms-auto rounded-lg border border-fog px-2 py-0.5 text-xs text-graphite">
                  {item.phase ? t("phaseBadge", { phase: item.phase }) : t("comingSoon")}
                </span>
              </span>
            );
          })}
        </div>
      ))}
    </nav>
  );
}

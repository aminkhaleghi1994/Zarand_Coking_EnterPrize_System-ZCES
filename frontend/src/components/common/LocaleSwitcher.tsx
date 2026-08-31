"use client";

import { useLocale, useTranslations } from "next-intl";

import { Link, usePathname } from "@/i18n/navigation";
import { routing } from "@/i18n/routing";

export function LocaleSwitcher() {
  const t = useTranslations("locale");
  const activeLocale = useLocale();
  const pathname = usePathname();

  return (
    <nav aria-label={t("switcher")} className="flex items-center gap-1">
      {routing.locales.map((locale) => (
        <Link
          key={locale}
          href={pathname}
          locale={locale}
          aria-current={locale === activeLocale ? "true" : undefined}
          className={`flex h-11 min-w-11 items-center justify-center rounded-md px-3 text-sm transition-colors duration-200 ${
            locale === activeLocale
              ? "bg-background/20 font-bold text-white"
              : "text-white/80 hover:text-white"
          }`}
        >
          {t(locale)}
        </Link>
      ))}
    </nav>
  );
}

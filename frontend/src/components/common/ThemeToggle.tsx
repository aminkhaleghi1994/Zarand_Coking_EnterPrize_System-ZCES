"use client";

import { Moon, Sun } from "lucide-react";
import { useTranslations } from "next-intl";
import { useTheme } from "next-themes";

import { cn } from "@/lib/utils";

export function ThemeToggle({ tone = "light" }: { tone?: "light" | "dark" }) {
  const t = useTranslations("theme");
  const { setTheme, resolvedTheme } = useTheme();

  return (
    <button
      type="button"
      onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
      title={t("toggle")}
      className={cn(
        "flex h-11 min-w-11 items-center justify-center rounded-md outline-none transition-colors duration-200 focus-visible:ring-2 focus-visible:ring-ring/50",
        tone === "dark"
          ? "text-white/80 hover:text-white"
          : "text-charcoal hover:text-ink",
      )}
    >
      <Sun aria-hidden className="size-5 dark:hidden" />
      <Moon aria-hidden className="hidden size-5 dark:block" />
      <span className="sr-only">{t("toggle")}</span>
    </button>
  );
}

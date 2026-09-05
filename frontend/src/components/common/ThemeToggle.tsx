"use client";

import { Moon, Sun } from "lucide-react";
import { useTranslations } from "next-intl";

import { THEME_STORAGE_KEY } from "@/lib/theme";
import { cn } from "@/lib/utils";

export function ThemeToggle({ tone = "light" }: { tone?: "light" | "dark" }) {
  const t = useTranslations("theme");

  const toggle = () => {
    const root = document.documentElement;
    const dark = !root.classList.contains("dark");
    root.classList.toggle("dark", dark);
    root.style.colorScheme = dark ? "dark" : "light";
    try {
      localStorage.setItem(THEME_STORAGE_KEY, dark ? "dark" : "light");
    } catch {}
  };

  return (
    <button
      type="button"
      onClick={toggle}
      title={t("toggle")}
      className={cn(
        "flex h-11 min-w-11 items-center justify-center rounded-md outline-none transition-colors duration-200 focus-visible:ring-2 focus-visible:ring-ring/50",
        tone === "dark"
          ? "text-white/80 hover:bg-white/10 hover:text-white"
          : "text-charcoal hover:bg-cloud hover:text-ink",
      )}
    >
      <Sun aria-hidden className="size-5 dark:hidden" />
      <Moon aria-hidden className="hidden size-5 dark:block" />
      <span className="sr-only">{t("toggle")}</span>
    </button>
  );
}

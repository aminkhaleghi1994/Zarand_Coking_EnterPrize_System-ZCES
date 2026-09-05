"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { cn } from "@/lib/utils";

import { CatalogView } from "./CatalogView";
import { StockView } from "./StockView";
import { WarehouseView } from "./WarehouseView";
import { AlertsView } from "./AlertsView";

type Tab = "catalog" | "warehouses" | "stock" | "alerts";

export function WarehouseConsole() {
  const t = useTranslations("warehouse");
  const [tab, setTab] = useState<Tab>("catalog");

  return (
    <div className="grid gap-6">
      <div role="tablist" aria-label={t("tabsLabel")} className="flex flex-wrap gap-1">
        {(["catalog", "warehouses", "stock", "alerts"] as Tab[]).map((value) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={tab === value}
            onClick={() => setTab(value)}
            className={cn(
              "flex h-11 items-center rounded-md px-5 text-sm outline-none transition-colors duration-200 focus-visible:ring-2 focus-visible:ring-ring/50",
              tab === value
                ? "bg-brand-soft font-bold text-brand-deep dark:text-brand-bright"
                : "text-charcoal hover:bg-cloud",
            )}
          >
            {t(`tabs.${value}`)}
          </button>
        ))}
      </div>

      {tab === "catalog" && <CatalogView />}
      {tab === "warehouses" && <WarehouseView />}
      {tab === "stock" && <StockView />}
      {tab === "alerts" && <AlertsView />}
    </div>
  );
}

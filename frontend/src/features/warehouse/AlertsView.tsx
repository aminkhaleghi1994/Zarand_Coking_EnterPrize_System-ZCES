"use client";

import { useQuery } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { warehouseApi, type StockAlert } from "@/lib/client-api";

import { formatWarehouseTimestamp } from "./shared";

type AlertFilter = "true" | "false" | "all";

export function AlertsView() {
  const t = useTranslations("warehouse.alerts");
  const locale = useLocale();
  const [filter, setFilter] = useState<AlertFilter>("true");

  const alertsQuery = useQuery({
    queryKey: ["warehouse-alerts", filter],
    queryFn: ({ signal }) => warehouseApi.alerts.list(filter, signal),
  });

  const alerts = alertsQuery.data?.ok ? alertsQuery.data.data.items : [];

  return (
    <div className="grid gap-6">
      <div role="group" aria-label={t("filterLabel")} className="flex gap-1">
        {(["true", "false", "all"] as AlertFilter[]).map((value) => (
          <button
            key={value}
            type="button"
            onClick={() => setFilter(value)}
            aria-pressed={filter === value}
            className={
              "flex h-11 items-center rounded-md px-4 text-sm outline-none transition-colors duration-200 focus-visible:ring-2 focus-visible:ring-ring/50 " +
              (filter === value
                ? "bg-brand-soft font-bold text-brand-deep dark:text-brand-bright"
                : "text-charcoal hover:bg-cloud")
            }
          >
            {t(`filter.${value}`)}
          </button>
        ))}
      </div>

      {alertsQuery.isPending ? (
        <div className="grid gap-2">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : (
        <ul className="grid gap-3">
          {alerts.map((alert: StockAlert) => (
            <li key={alert.id} className="rounded-xl border border-fog bg-canvas p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="font-bold">
                  {alert.item.name}
                  <span className="ms-2 text-xs text-graphite">{alert.item.code ?? "—"}</span>
                </p>
                <span className="rounded-lg bg-bloom-wine/10 px-2 py-0.5 text-xs font-bold text-bloom-deep">
                  {alert.resolved_at
                    ? t("resolved", {
                        date: formatWarehouseTimestamp(alert.resolved_at, locale),
                      })
                    : t("activeBadge")}
                </span>
              </div>
              <p className="mt-1 text-sm text-charcoal">
                {t("location", {
                  warehouse: alert.warehouse.name,
                  shelf: alert.shelf.code,
                })}
              </p>
              <p className="text-sm text-charcoal">
                {t("quantities", {
                  quantityAtAlert: alert.quantity_at_alert,
                  threshold: alert.threshold_at_alert,
                  current: alert.current_quantity,
                })}
              </p>
              <p className="text-xs text-graphite">
                {t("raisedAt", { date: formatWarehouseTimestamp(alert.raised_at, locale) })}
              </p>
            </li>
          ))}
          {alerts.length === 0 ? (
            <li className="p-6 text-center text-graphite">{t("empty")}</li>
          ) : null}
        </ul>
      )}
    </div>
  );
}

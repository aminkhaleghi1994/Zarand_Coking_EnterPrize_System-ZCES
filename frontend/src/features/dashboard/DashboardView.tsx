"use client";

import { useQuery } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";

import { Skeleton } from "@/components/ui/skeleton";
import { reportsApi, type DashboardCounters } from "@/lib/client-api";

import { useFeatureFlags } from "@/features/settings/useFeatureFlags";

const COUNTERS: { key: keyof DashboardCounters; tone: "brand" | "plain" }[] = [
  { key: "active_employees", tone: "plain" },
  { key: "open_item_requests", tone: "brand" },
  { key: "active_loans", tone: "plain" },
  { key: "unresolved_low_stock_alerts", tone: "brand" },
  { key: "catalog_items", tone: "plain" },
  { key: "delivered_notifications", tone: "plain" },
];

function BreakdownCard({
  title,
  entries,
  labelLocale,
}: {
  title: string;
  entries: Record<string, number>;
  labelLocale: (key: string) => string;
}) {
  return (
    <div className="rounded-2xl border border-fog bg-canvas p-6 shadow-soft-lift">
      <h3 className="font-bold">{title}</h3>
      <ul className="mt-4 grid gap-2">
        {Object.entries(entries).map(([key, count]) => (
          <li
            key={key}
            className="flex items-center justify-between gap-4 border-b border-fog pb-2 text-sm last:border-b-0 last:pb-0"
          >
            <span className="text-charcoal">{labelLocale(key)}</span>
            <span className="font-bold tabular-nums">{count}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * Management dashboard (T018, US3): scope-filtered counters and breakdowns
 * honoring the dashboard.show_* settings flags. Numbers arrive composed
 * from the backend contracts — a Workplace-scoped manager sees their own
 * world, not the company's.
 */
export function DashboardView() {
  const t = useTranslations("dashboard.report");
  const locale = useLocale();
  const { flags } = useFeatureFlags();

  const dashboardQuery = useQuery({
    queryKey: ["reports", "dashboard"],
    queryFn: ({ signal }) => reportsApi.dashboard(signal),
  });

  if (dashboardQuery.isPending) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {COUNTERS.map((counter) => (
          <Skeleton key={counter.key} className="h-28 w-full rounded-2xl" />
        ))}
      </div>
    );
  }

  if (!dashboardQuery.data?.ok) {
    return (
      <p className="rounded-xl border border-fog bg-canvas p-6 text-sm text-charcoal">
        {t("loadError")}
      </p>
    );
  }

  const { counters, item_requests_by_status, loans_by_status, low_stock_alerts_by_warehouse } =
    dashboardQuery.data.data;

  return (
    <div className="grid gap-6">
      <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {COUNTERS.map(({ key, tone }) => (
          <li
            key={key}
            className="flex flex-col gap-2 rounded-2xl border border-fog bg-canvas p-6 shadow-soft-lift"
          >
            <span className="text-xs font-bold uppercase tracking-widest text-graphite">
              {t(`counters.${key}`)}
            </span>
            <span
              className={
                "text-4xl font-black tabular-nums " +
                (tone === "brand" ? "text-brand dark:text-brand-bright" : "text-ink")
              }
            >
              {counters[key].toLocaleString(locale === "fa" ? "fa-IR" : "en-GB")}
            </span>
          </li>
        ))}
      </ul>

      <div className="grid gap-4 md:grid-cols-2">
        {flags.showRequestsBreakdown ? (
          <BreakdownCard
            title={t("requestsBreakdown")}
            entries={item_requests_by_status}
            labelLocale={(key) => t(`requestStatus.${key}`)}
          />
        ) : null}
        {flags.showAlertsBreakdown ? (
          <div className="grid gap-4">
            <BreakdownCard
              title={t("loansBreakdown")}
              entries={loans_by_status}
              labelLocale={(key) => t(`loanStatus.${key}`)}
            />
            {low_stock_alerts_by_warehouse.length > 0 ? (
              <div className="rounded-2xl border border-fog bg-canvas p-6 shadow-soft-lift">
                <h3 className="font-bold">{t("alertsBreakdown")}</h3>
                <ul className="mt-4 grid gap-2">
                  {low_stock_alerts_by_warehouse.map((entry) => (
                    <li
                      key={entry.warehouse_code}
                      className="flex items-center justify-between gap-4 border-b border-fog pb-2 text-sm last:border-b-0 last:pb-0"
                    >
                      <span className="truncate text-charcoal">
                        {entry.warehouse_name}
                      </span>
                      <span className="font-bold tabular-nums text-bloom-deep">
                        {entry.count}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}

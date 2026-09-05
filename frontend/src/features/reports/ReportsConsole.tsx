"use client";

import { useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import {
  reportsApi,
  type AuditReportRow,
  type InventoryReportRow,
  type LoanReportRow,
  type RequestReportRow,
} from "@/lib/client-api";

type ReportTabKey = "inventory" | "requests" | "loans" | "audit";

const PAGE_SIZE = 20;

function formatTimestamp(iso: string | null, locale: string): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return locale === "fa"
    ? date.toLocaleString("fa-IR-u-ca-persian", { hour12: false })
    : date.toLocaleString("en-GB", { hour12: false });
}

/**
 * Reports console (T019, US1/US2): four permission-gated tabs over the
 * operational reports, with per-tab filters, paginated tables (cards on
 * small screens), and Excel export of the current filtered page.
 */
export function ReportsConsole({ permissions }: { permissions: string[] }) {
  const t = useTranslations("reports");
  const locale = useLocale();

  const tabs: { key: ReportTabKey; permission: string }[] = [
    { key: "inventory", permission: "reports:inventory:read" },
    { key: "requests", permission: "reports:request:read" },
    { key: "loans", permission: "reports:loan:read" },
    { key: "audit", permission: "audit:log:read" },
  ];
  const available = tabs.filter((tabItem) => permissions.includes(tabItem.permission));
  const [tab, setTab] = useState<ReportTabKey>(available[0]?.key ?? "inventory");
  const activeTab = available.find((item) => item.key === tab) ?? available[0];
  const [page, setPage] = useState(1);

  // per-tab filter state
  const [belowMinOnly, setBelowMinOnly] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [actionFilter, setActionFilter] = useState<string>("");

  const canExport = permissions.includes("reports:export:excel");

  const inventoryQuery = useQuery({
    queryKey: ["reports", "inventory", page, belowMinOnly],
    queryFn: ({ signal }) =>
      reportsApi.inventory({ page, pageSize: PAGE_SIZE, belowMinOnly }, signal),
    enabled: activeTab?.key === "inventory",
  });
  const requestsQuery = useQuery({
    queryKey: ["reports", "requests", page, statusFilter],
    queryFn: ({ signal }) =>
      reportsApi.requests(
        { page, pageSize: PAGE_SIZE, status: statusFilter || undefined },
        signal,
      ),
    enabled: activeTab?.key === "requests",
  });
  const loansQuery = useQuery({
    queryKey: ["reports", "loans"],
    queryFn: ({ signal }) => reportsApi.loans({}, signal),
    enabled: activeTab?.key === "loans",
  });
  const auditQuery = useQuery({
    queryKey: ["reports", "audit", page, actionFilter],
    queryFn: ({ signal }) =>
      reportsApi.audit(
        { page, pageSize: PAGE_SIZE, action: actionFilter || undefined },
        signal,
      ),
    enabled: activeTab?.key === "audit",
  });

  if (available.length === 0) {
    return (
      <p className="rounded-xl border border-fog bg-canvas p-6 text-charcoal">
        {t("noAccess")}
      </p>
    );
  }

  const exportParams: Record<string, string | number | boolean | undefined> = {
    page,
    pageSize: PAGE_SIZE,
    ...(activeTab?.key === "inventory" ? { below_min_only: belowMinOnly } : {}),
    ...(activeTab?.key === "requests" ? { status: statusFilter || undefined } : {}),
    ...(activeTab?.key === "audit" ? { action: actionFilter || undefined } : {}),
  };

  const pager = (total: number) => {
    const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
    return (
      <div className="flex items-center justify-between gap-4">
        <button
          type="button"
          disabled={page <= 1}
          onClick={() => setPage((value) => Math.max(1, value - 1))}
          className="h-11 rounded-md border border-fog bg-canvas px-4 text-sm font-bold disabled:opacity-40"
        >
          {t("prevPage")}
        </button>
        <span className="text-sm text-graphite tabular-nums">
          {t("pageOf", { page, pages })}
        </span>
        <button
          type="button"
          disabled={page >= pages}
          onClick={() => setPage((value) => value + 1)}
          className="h-11 rounded-md border border-fog bg-canvas px-4 text-sm font-bold disabled:opacity-40"
        >
          {t("nextPage")}
        </button>
      </div>
    );
  };

  return (
    <div className="grid gap-6">
      <div role="group" aria-label={t("tabsLabel")} className="flex flex-wrap gap-1">
        {available.map((item) => (
          <button
            key={item.key}
            type="button"
            onClick={() => {
              setTab(item.key);
              setPage(1);
            }}
            aria-pressed={tab === item.key}
            className={
              "flex h-11 items-center rounded-md px-4 text-sm outline-none transition-colors duration-200 focus-visible:ring-2 focus-visible:ring-ring/50 " +
              (tab === item.key
                ? "bg-brand-soft font-bold text-brand-deep dark:text-brand-bright"
                : "text-charcoal hover:bg-cloud")
            }
          >
            {t(`tabs.${item.key}`)}
          </button>
        ))}
      </div>

      {tab === "inventory" ? (
        <section aria-label={t("tabs.inventory")} className="grid gap-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <label className="flex items-center gap-2 text-sm text-charcoal">
              <input
                type="checkbox"
                checked={belowMinOnly}
                onChange={(event) => {
                  setBelowMinOnly(event.target.checked);
                  setPage(1);
                }}
                className="size-4 accent-brand"
              />
              {t("filters.belowMinOnly")}
            </label>
            {canExport ? (
              <a
                href={reportsApi.exportUrl("inventory", exportParams, locale)}
                className="flex h-11 items-center gap-2 rounded-md bg-brand px-4 text-sm font-bold uppercase tracking-[0.7px] text-white transition-colors duration-200 hover:bg-brand-deep"
              >
                <Download aria-hidden className="size-4" />
                {t("export")}
              </a>
            ) : null}
          </div>
          {inventoryQuery.isPending ? (
            <Skeleton className="h-40 w-full rounded-xl" />
          ) : !inventoryQuery.data?.ok ? (
            <p className="rounded-xl border border-fog bg-canvas p-6 text-sm text-charcoal">
              {t("loadError")}
            </p>
          ) : (
            <>
              <InventoryTable rows={inventoryQuery.data.data.items} locale={locale} />
              {pager(inventoryQuery.data.data.total)}
            </>
          )}
        </section>
      ) : null}

      {tab === "requests" ? (
        <section aria-label={t("tabs.requests")} className="grid gap-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div role="group" aria-label={t("filters.statusLabel")} className="flex gap-1">
              {["", "pending", "approved", "rejected", "fulfilled"].map((value) => (
                <button
                  key={value || "all"}
                  type="button"
                  onClick={() => {
                    setStatusFilter(value);
                    setPage(1);
                  }}
                  aria-pressed={statusFilter === value}
                  className={
                    "flex h-11 items-center rounded-md px-3 text-xs font-bold uppercase tracking-wide outline-none transition-colors duration-200 " +
                    (statusFilter === value
                      ? "bg-brand text-white"
                      : "border border-fog bg-canvas text-charcoal hover:bg-cloud")
                  }
                >
                  {value ? t(`status.${value}`) : t("filters.all")}
                </button>
              ))}
            </div>
            {canExport ? (
              <a
                href={reportsApi.exportUrl("requests", exportParams, locale)}
                className="flex h-11 items-center gap-2 rounded-md bg-brand px-4 text-sm font-bold uppercase tracking-[0.7px] text-white transition-colors duration-200 hover:bg-brand-deep"
              >
                <Download aria-hidden className="size-4" />
                {t("export")}
              </a>
            ) : null}
          </div>
          {requestsQuery.isPending ? (
            <Skeleton className="h-40 w-full rounded-xl" />
          ) : !requestsQuery.data?.ok ? (
            <p className="rounded-xl border border-fog bg-canvas p-6 text-sm text-charcoal">
              {t("loadError")}
            </p>
          ) : (
            <>
              {requestsQuery.data.data.status_counts &&
              Object.values(requestsQuery.data.data.status_counts).some(
                (count) => count > 0,
              ) ? (
                <p className="text-sm text-charcoal">
                  {t("statusCounts", {
                    pending: requestsQuery.data.data.status_counts.pending ?? 0,
                    approved: requestsQuery.data.data.status_counts.approved ?? 0,
                    rejected: requestsQuery.data.data.status_counts.rejected ?? 0,
                    fulfilled: requestsQuery.data.data.status_counts.fulfilled ?? 0,
                  })}
                </p>
              ) : null}
              <RequestTable rows={requestsQuery.data.data.items} locale={locale} />
              {pager(requestsQuery.data.data.total)}
            </>
          )}
        </section>
      ) : null}

      {tab === "loans" ? (
        <section aria-label={t("tabs.loans")} className="grid gap-4">
          {canExport ? (
            <div className="flex justify-end">
              <a
                href={reportsApi.exportUrl("loans", {}, locale)}
                className="flex h-11 items-center gap-2 rounded-md bg-brand px-4 text-sm font-bold uppercase tracking-[0.7px] text-white transition-colors duration-200 hover:bg-brand-deep"
              >
                <Download aria-hidden className="size-4" />
                {t("export")}
              </a>
            </div>
          ) : null}
          {loansQuery.isPending ? (
            <Skeleton className="h-40 w-full rounded-xl" />
          ) : !loansQuery.data?.ok ? (
            <p className="rounded-xl border border-fog bg-canvas p-6 text-sm text-charcoal">
              {t("loadError")}
            </p>
          ) : loansQuery.data.data.length === 0 ? (
            <p className="rounded-xl border border-fog bg-canvas p-6 text-sm text-graphite">
              {t("empty")}
            </p>
          ) : (
            <LoanTable rows={loansQuery.data.data} locale={locale} />
          )}
        </section>
      ) : null}

      {tab === "audit" ? (
        <section aria-label={t("tabs.audit")} className="grid gap-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <input
              type="text"
              value={actionFilter}
              placeholder={t("filters.actionPlaceholder")}
              onChange={(event) => {
                setActionFilter(event.target.value);
                setPage(1);
              }}
              className="h-11 w-56 rounded-md border border-fog bg-canvas px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
              aria-label={t("filters.actionPlaceholder")}
            />
            {canExport ? (
              <a
                href={reportsApi.exportUrl("audit", exportParams, locale)}
                className="flex h-11 items-center gap-2 rounded-md bg-brand px-4 text-sm font-bold uppercase tracking-[0.7px] text-white transition-colors duration-200 hover:bg-brand-deep"
              >
                <Download aria-hidden className="size-4" />
                {t("export")}
              </a>
            ) : null}
          </div>
          {auditQuery.isPending ? (
            <Skeleton className="h-40 w-full rounded-xl" />
          ) : !auditQuery.data?.ok ? (
            <p className="rounded-xl border border-fog bg-canvas p-6 text-sm text-charcoal">
              {t("loadError")}
            </p>
          ) : (
            <>
              <AuditTable rows={auditQuery.data.data.items} locale={locale} />
              {pager(auditQuery.data.data.total)}
            </>
          )}
        </section>
      ) : null}
    </div>
  );
}

function InventoryTable({
  rows,
  locale,
}: {
  rows: InventoryReportRow[];
  locale: string;
}) {
  const t = useTranslations("reports.inventory");
  return (
    <ul className="grid gap-2">
      {rows.map((row) => (
        <li
          key={`${row.item_id}-${row.warehouse_code}-${row.shelf_code}`}
          className="rounded-xl border border-fog bg-canvas p-4"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="font-bold">
              {locale === "fa" ? row.item_name_fa : row.item_name}
              <span className="ms-2 text-xs text-graphite">{row.item_code ?? "—"}</span>
            </p>
            {row.below_min ? (
              <span className="rounded-lg bg-bloom-wine/10 px-2 py-0.5 text-xs font-bold text-bloom-deep">
                {t("belowMin")}
              </span>
            ) : null}
          </div>
          <p className="mt-1 text-sm text-charcoal">
            {t("location", { warehouse: row.warehouse_name, shelf: row.shelf_code })}
          </p>
          <p className="text-sm text-charcoal">
            {t("quantities", {
              quantity: row.quantity,
              threshold: row.threshold,
              unit: row.unit,
            })}
          </p>
        </li>
      ))}
      {rows.length === 0 ? (
        <li className="p-6 text-center text-sm text-graphite">{t("empty")}</li>
      ) : null}
    </ul>
  );
}

function RequestTable({ rows, locale }: { rows: RequestReportRow[]; locale: string }) {
  const t = useTranslations("reports.requests");
  return (
    <ul className="grid gap-2">
      {rows.map((row) => (
        <li key={row.id} className="rounded-xl border border-fog bg-canvas p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="font-bold">{row.purpose_description}</p>
            <span className="rounded-lg bg-brand-soft px-2 py-0.5 text-xs font-bold text-brand-deep dark:text-brand-bright">
              {t(`status.${row.status}`)}
            </span>
          </div>
          <p className="mt-1 text-sm text-charcoal">
            {t("requester", { email: row.requested_by_email ?? "—" })} ·{" "}
            {t("lines", { count: row.line_count })}
          </p>
          <p className="text-xs text-graphite">
            {formatTimestamp(row.created_at, locale)}
          </p>
        </li>
      ))}
      {rows.length === 0 ? (
        <li className="p-6 text-center text-sm text-graphite">{t("empty")}</li>
      ) : null}
    </ul>
  );
}

function LoanTable({ rows, locale }: { rows: LoanReportRow[]; locale: string }) {
  const t = useTranslations("reports.loans");
  return (
    <ul className="grid gap-2">
      {rows.map((row) => (
        <li
          key={`${row.workplace_id}-${row.year}`}
          className="rounded-xl border border-fog bg-canvas p-4"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="font-bold">
              {locale === "fa" ? row.workplace_name_fa : row.workplace_name}
            </p>
            <span className="text-xs font-bold text-graphite tabular-nums">
              {t("year", { year: row.year.toLocaleString(locale === "fa" ? "fa-IR" : "en-GB") })}
            </span>
          </div>
          <p className="mt-1 text-sm text-charcoal">
            {t("counts", {
              total: row.requests_total,
              pending: row.requests_pending,
              active: row.requests_active,
              settled: row.requests_settled,
              cancelled: row.requests_cancelled,
            })}
          </p>
          <p className="text-sm text-charcoal">
            {t("commitments", {
              loan: row.active_loan_commitment,
              guarantee: row.active_guarantee_commitment,
            })}
          </p>
          {row.policy_max_loan ? (
            <p className="text-xs text-graphite">
              {t("caps", { loan: row.policy_max_loan, guarantee: row.policy_max_guarantee })}
            </p>
          ) : (
            <p className="text-xs text-graphite">{t("noPolicy")}</p>
          )}
        </li>
      ))}
    </ul>
  );
}

function AuditTable({ rows, locale }: { rows: AuditReportRow[]; locale: string }) {
  const t = useTranslations("reports.audit");
  return (
    <ul className="grid gap-2">
      {rows.map((row) => (
        <li key={row.id} className="rounded-xl border border-fog bg-canvas p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="font-mono text-sm font-bold">{row.action}</p>
            <span className="text-xs text-graphite">
              {formatTimestamp(row.created_at, locale)}
            </span>
          </div>
          <p className="mt-1 text-sm text-charcoal">
            {t("entity", { type: row.entity_type })}
          </p>
          {row.after_snapshot ? (
            <p className="mt-1 break-words font-mono text-xs text-charcoal">
              {Object.entries(row.after_snapshot)
                .map(([key, value]) => `${key}=${String(value)}`)
                .join("; ")}
            </p>
          ) : null}
          {row.trace_id ? (
            <p className="mt-1 font-mono text-xs text-graphite">{row.trace_id}</p>
          ) : null}
        </li>
      ))}
      {rows.length === 0 ? (
        <li className="p-6 text-center text-sm text-graphite">{t("empty")}</li>
      ) : null}
    </ul>
  );
}

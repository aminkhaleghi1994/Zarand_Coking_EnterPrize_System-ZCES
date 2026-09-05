"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  assetApi,
  warehouseApi,
  type ApiError,
  type AssetRecord,
} from "@/lib/client-api";
import { cn } from "@/lib/utils";
import { warehouseErrorMessage } from "@/features/warehouse/shared";

import { AssetForm } from "./AssetForm";
import { AssignDialog } from "./AssignDialog";
import { HistoryDrawer } from "./HistoryDrawer";

type StatusFilter = "all" | "available" | "assigned" | "retired";

const PAGE_SIZE = 20;

export function AssetsView() {
  const t = useTranslations("assets");
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<StatusFilter>("all");
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [page, setPage] = useState(1);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<AssetRecord | null>(null);
  const [assigning, setAssigning] = useState<AssetRecord | null>(null);
  const [historyFor, setHistoryFor] = useState<AssetRecord | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const identity = useQuery({
    queryKey: ["me"],
    queryFn: ({ signal }) => warehouseApi.me(signal),
  });
  const listQuery = useQuery({
    queryKey: ["warehouse-assets", { filter, search: debouncedSearch, page }],
    queryFn: ({ signal }) =>
      assetApi.list(
        {
          status: filter,
          search: debouncedSearch || undefined,
          page,
          pageSize: PAGE_SIZE,
        },
        signal,
      ),
  });

  const permissions = identity.data?.ok ? identity.data.data.permissions : [];
  const canCreate = permissions.includes("warehouse:asset:create");
  const canUpdate = permissions.includes("warehouse:asset:update");
  const canRetire = permissions.includes("warehouse:asset:retire");
  const canAssign = permissions.includes("warehouse:asset:assign");
  const canReturn = permissions.includes("warehouse:asset:return");

  const returnAsset = useMutation({
    mutationFn: (asset: AssetRecord) => assetApi.returnAsset(asset.id, asset.version),
    onSuccess: () => {
      setActionError(null);
      void queryClient.invalidateQueries({ queryKey: ["warehouse-assets"] });
    },
    onError: (error: ApiError) => setActionError(warehouseErrorMessage(t, error)),
  });

  const retireAsset = useMutation({
    mutationFn: (asset: AssetRecord) => assetApi.retire(asset.id, asset.version),
    onSuccess: () => {
      setActionError(null);
      void queryClient.invalidateQueries({ queryKey: ["warehouse-assets"] });
    },
    onError: (error: ApiError) => setActionError(warehouseErrorMessage(t, error)),
  });

  const assets = listQuery.data?.ok ? listQuery.data.data.items : [];
  const total = listQuery.data?.ok ? listQuery.data.data.total : 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const onSearchChange = (value: string) => {
    setSearch(value);
    window.clearTimeout(
      (window as unknown as { __assetSearchTimer?: number }).__assetSearchTimer,
    );
    (window as unknown as { __assetSearchTimer?: number }).__assetSearchTimer =
      window.setTimeout(() => {
        setDebouncedSearch(value);
        setPage(1);
      }, 300);
  };

  const refresh = () => {
    setActionError(null);
    void queryClient.invalidateQueries({ queryKey: ["warehouse-assets"] });
  };

  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-center gap-3">
        <Input
          type="search"
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder={t("searchPlaceholder")}
          aria-label={t("searchLabel")}
          className="h-11 w-full max-w-xs rounded-md"
        />
        <div role="group" aria-label={t("filterLabel")} className="flex flex-wrap gap-1">
          {(["all", "available", "assigned", "retired"] as StatusFilter[]).map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => {
                setFilter(value);
                setPage(1);
              }}
              aria-pressed={filter === value}
              className={cn(
                "flex h-11 items-center rounded-md px-4 text-sm outline-none transition-colors duration-200 focus-visible:ring-2 focus-visible:ring-ring/50",
                filter === value
                  ? "bg-brand-soft font-bold text-brand-deep dark:text-brand-bright"
                  : "text-charcoal hover:bg-cloud",
              )}
            >
              {t(`status.${value}`)}
            </button>
          ))}
        </div>
        {canCreate ? (
          <Button
            type="button"
            onClick={() => setCreating((current) => !current)}
            className="ms-auto h-11 rounded-md"
          >
            {t("compose")}
          </Button>
        ) : null}
      </div>

      {actionError ? (
        <p role="alert" className="text-sm font-bold text-bloom-deep">
          {actionError}
        </p>
      ) : null}

      {creating && canCreate ? (
        <AssetForm
          onCancel={() => setCreating(false)}
          onSaved={() => {
            setCreating(false);
            refresh();
          }}
        />
      ) : null}

      {editing && canUpdate ? (
        <AssetForm
          asset={editing}
          onCancel={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            refresh();
          }}
        />
      ) : null}

      {listQuery.isPending ? (
        <div className="grid gap-2">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-2/3" />
        </div>
      ) : listQuery.isError ? (
        <p className="p-6 text-sm font-bold text-bloom-deep">{t("errors.generic")}</p>
      ) : assets.length === 0 ? (
        <p className="p-6 text-center text-graphite">{t("empty")}</p>
      ) : (
        <>
          <div className="overflow-x-auto rounded-xl border border-fog bg-canvas shadow-soft-lift">
            <table className="hidden w-full min-w-[720px] text-sm md:table">
              <thead>
                <tr className="border-b border-fog text-xs uppercase tracking-wide text-graphite">
                  <th className="p-4 text-start font-bold">{t("table.asset")}</th>
                  <th className="p-4 text-start font-bold">{t("table.serial")}</th>
                  <th className="p-4 text-start font-bold">{t("table.status")}</th>
                  <th className="p-4 text-start font-bold">{t("table.holder")}</th>
                  <th className="p-4 text-start font-bold">{t("table.actions")}</th>
                </tr>
              </thead>
              <tbody>
                {assets.map((asset) => (
                  <tr key={asset.id} className="border-b border-fog last:border-b-0">
                    <td className="p-4">
                      <p className="font-bold">{asset.name}</p>
                      <p className="text-xs text-graphite" dir="rtl">
                        {asset.name_fa}
                      </p>
                    </td>
                    <td className="p-4" dir="ltr">
                      {asset.serial}
                    </td>
                    <td className="p-4">
                      <StatusBadge asset={asset} />
                    </td>
                    <td className="p-4">{holderLabel(t, asset)}</td>
                    <td className="p-4">
                      <div className="flex flex-wrap gap-2">
                        {asset.status === "available" && canAssign ? (
                          <RowButton label={t("assign.title")} onClick={() => setAssigning(asset)} />
                        ) : null}
                        {asset.status === "assigned" && canReturn ? (
                          <RowButton
                            label={t("returnAction.submit")}
                            destructive
                            confirmLabel={t("returnAction.submit")}
                            onClick={() => returnAsset.mutate(asset)}
                          />
                        ) : null}
                        {asset.status !== "retired" && canUpdate ? (
                          <RowButton label={t("form.edit")} onClick={() => setEditing(asset)} />
                        ) : null}
                        {asset.status === "available" && canRetire ? (
                          <RowButton
                            label={t("retire.submit")}
                            destructive
                            confirmLabel={t("retire.submit")}
                            onClick={() => retireAsset.mutate(asset)}
                          />
                        ) : null}
                        <RowButton label={t("history.title")} onClick={() => setHistoryFor(asset)} />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <ul className="grid gap-3 p-4 md:hidden">
              {assets.map((asset) => (
                <li key={asset.id} className="grid gap-2 rounded-lg border border-fog p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="font-bold">{asset.name}</p>
                    <StatusBadge asset={asset} />
                  </div>
                  <p className="text-xs text-graphite" dir="rtl">
                    {asset.name_fa}
                  </p>
                  <p className="text-sm" dir="ltr">
                    {asset.serial}
                  </p>
                  <p className="text-sm text-charcoal">{holderLabel(t, asset)}</p>
                  <div className="flex flex-wrap gap-2">
                    {asset.status === "available" && canAssign ? (
                      <RowButton label={t("assign.title")} onClick={() => setAssigning(asset)} />
                    ) : null}
                    {asset.status === "assigned" && canReturn ? (
                      <RowButton
                        label={t("returnAction.submit")}
                        destructive
                        confirmLabel={t("returnAction.submit")}
                        onClick={() => returnAsset.mutate(asset)}
                      />
                    ) : null}
                    {asset.status !== "retired" && canUpdate ? (
                      <RowButton label={t("form.edit")} onClick={() => setEditing(asset)} />
                    ) : null}
                    {asset.status === "available" && canRetire ? (
                      <RowButton
                        label={t("retire.submit")}
                        destructive
                        confirmLabel={t("retire.submit")}
                        onClick={() => retireAsset.mutate(asset)}
                      />
                    ) : null}
                    <RowButton label={t("history.title")} onClick={() => setHistoryFor(asset)} />
                  </div>
                </li>
              ))}
            </ul>
          </div>

          {totalPages > 1 ? (
            <nav aria-label={t("filterLabel")} className="flex items-center gap-3">
              <Button
                type="button"
                variant="outline"
                disabled={page <= 1}
                onClick={() => setPage((current) => current - 1)}
                className="h-11 rounded-md px-4"
              >
                ‹
              </Button>
              <span className="text-sm text-charcoal">
                {page} / {totalPages}
              </span>
              <Button
                type="button"
                variant="outline"
                disabled={page >= totalPages}
                onClick={() => setPage((current) => current + 1)}
                className="h-11 rounded-md px-4"
              >
                ›
              </Button>
            </nav>
          ) : null}
        </>
      )}

      {assigning ? (
        <AssignDialog
          asset={assigning}
          onClose={() => setAssigning(null)}
          onAssigned={refresh}
        />
      ) : null}

      {historyFor ? (
        <HistoryDrawer asset={historyFor} onClose={() => setHistoryFor(null)} />
      ) : null}
    </div>
  );
}

function holderLabel(t: { (key: string): string }, asset: AssetRecord): string {
  if (asset.status === "retired") return "—";
  if (asset.holder.type === "employee" && asset.holder.employee) {
    return `${t("holder.employee")}: ${asset.holder.employee.name}`;
  }
  if (asset.holder.type === "location" && asset.holder.location) {
    return `${t("holder.location")}: ${asset.holder.location}`;
  }
  return t("holder.available");
}

function StatusBadge({ asset }: { asset: AssetRecord }) {
  const t = useTranslations("assets");
  return (
    <span
      className={cn(
        "inline-block rounded-lg px-2 py-0.5 text-xs font-bold",
        asset.status === "retired"
          ? "bg-cloud text-graphite"
          : asset.status === "assigned"
            ? "bg-cloud text-ink"
            : "bg-brand-soft text-brand-deep dark:text-brand-bright",
      )}
    >
      {t(`status.${asset.status}`)}
    </span>
  );
}

function RowButton({
  label,
  onClick,
  destructive,
  confirmLabel,
}: {
  label: string;
  onClick: () => void;
  destructive?: boolean;
  confirmLabel?: string;
}) {
  const [confirming, setConfirming] = useState(false);
  if (confirming) {
    return (
      <span className="flex gap-1">
        <button
          type="button"
          onClick={() => {
            setConfirming(false);
            onClick();
          }}
          className="flex h-9 items-center rounded-md bg-bloom-deep px-3 text-xs font-bold text-white transition-colors duration-200"
        >
          {confirmLabel ?? label}
        </button>
        <button
          type="button"
          onClick={() => setConfirming(false)}
          className="flex h-9 items-center rounded-md px-2 text-xs text-graphite hover:text-ink"
        >
          ✕
        </button>
      </span>
    );
  }
  return (
    <button
      type="button"
      onClick={() => (destructive ? setConfirming(true) : onClick())}
      className={cn(
        "flex h-9 items-center rounded-md border border-fog px-3 text-xs font-bold outline-none transition-colors duration-200 focus-visible:ring-2 focus-visible:ring-ring/50",
        destructive
          ? "text-bloom-deep hover:bg-bloom-deep/10"
          : "text-charcoal hover:bg-cloud hover:text-ink",
      )}
    >
      {label}
    </button>
  );
}

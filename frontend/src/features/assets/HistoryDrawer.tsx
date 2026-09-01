"use client";

import { useInfiniteQuery, useQueryClient } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { assetApi, type AssetRecord, type HistoryHolder } from "@/lib/client-api";
import { cn } from "@/lib/utils";
import { formatWarehouseTimestamp } from "@/features/warehouse/shared";

const HISTORY_PAGE_SIZE = 100;

export function HistoryDrawer({ asset, onClose }: { asset: AssetRecord; onClose: () => void }) {
  const t = useTranslations("assets.history");
  const locale = useLocale();
  const queryClient = useQueryClient();
  const historyQuery = useInfiniteQuery({
    queryKey: ["asset-history", asset.id],
    queryFn: async ({ pageParam, signal }) => {
      const result = await assetApi.history(asset.id, pageParam as number, signal);
      if (!result.ok) {
        throw new Error(result.error.code);
      }
      return result.data;
    },
    initialPageParam: 1,
    getNextPageParam: (lastPage, allPages) => {
      const fetched = allPages.length * HISTORY_PAGE_SIZE;
      return fetched < lastPage.total ? allPages.length + 1 : undefined;
    },
  });
  const entries = historyQuery.data
    ? historyQuery.data.pages.flatMap((page) => page.items)
    : [];

  return (
    <div className="fixed inset-0 z-40 flex items-stretch justify-end">
      <div
        role="presentation"
        onClick={onClose}
        className="absolute inset-0 bg-black/40 motion-safe:animate-in motion-safe:fade-in-0 motion-safe:duration-200"
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label={t("title")}
        className="relative flex w-full max-w-md flex-col gap-4 overflow-y-auto border-fog bg-canvas p-6 shadow-floating-modal md:border-s"
      >
        <div className="flex items-center justify-between gap-2">
          <h3 className="text-lg font-bold">{t("title")}</h3>
          <button
            type="button"
            onClick={() => {
              void queryClient.removeQueries({ queryKey: ["asset-history", asset.id] });
              onClose();
            }}
            aria-label={t("title")}
            className="flex h-9 w-9 items-center justify-center rounded-md text-graphite transition-colors duration-200 hover:bg-cloud hover:text-ink"
          >
            ✕
          </button>
        </div>
        <div className="grid gap-1">
          <p className="font-bold">{asset.name}</p>
          <p className="text-xs text-graphite" dir="ltr">
            {asset.serial}
          </p>
        </div>

        {historyQuery.isPending ? (
          <div className="grid gap-3">
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-20 w-full" />
          </div>
        ) : entries.length === 0 ? (
          <p className="text-sm text-charcoal">{t("empty")}</p>
        ) : (
          <>
            <ol className="grid gap-0 border-fog">
              {entries.map((entry, index) => (
                <li key={entry.id} className="relative grid gap-1 pb-6 ps-6">
                  {index < entries.length - 1 || historyQuery.hasNextPage ? (
                    <span
                      aria-hidden="true"
                      className="absolute inset-y-0 start-[7px] w-px bg-fog"
                    />
                  ) : null}
                  <span
                    aria-hidden="true"
                    className={cn(
                      "absolute start-0 top-1 h-3.5 w-3.5 rounded-full border-2",
                      entry.action === "retired"
                        ? "border-bloom-deep bg-bloom-deep/20"
                        : "border-brand bg-brand-soft",
                    )}
                  />
                  <p className="text-sm font-bold">{t(`action.${entry.action}`)}</p>
                  <p className="text-xs text-graphite">
                    {formatWarehouseTimestamp(entry.created_at, locale)}
                  </p>
                  <HolderLine label={t("from")} holder={entry.from_holder} />
                  <HolderLine label={t("to")} holder={entry.to_holder} />
                  {entry.note ? (
                    <p className="text-xs text-charcoal">
                      {t("note")}: {entry.note}
                    </p>
                  ) : null}
                </li>
              ))}
            </ol>
            {historyQuery.hasNextPage ? (
              <Button
                type="button"
                variant="outline"
                onClick={() => void historyQuery.fetchNextPage()}
                disabled={historyQuery.isFetchingNextPage}
                className="h-11 rounded-md"
              >
                {historyQuery.isFetchingNextPage ? t("loadingMore") : t("loadMore")}
              </Button>
            ) : null}
          </>
        )}
      </aside>
    </div>
  );
}

function holderText(holder: HistoryHolder | null): string | null {
  if (!holder) return null;
  if (holder.type === "employee" && holder.employee) return holder.employee.name;
  if (holder.type === "location" && holder.location) return holder.location;
  if (holder.type === "available") return "—";
  return null;
}

function HolderLine({ label, holder }: { label: string; holder: HistoryHolder | null }) {
  const text = holderText(holder);
  if (!text) return null;
  return (
    <p className="text-xs text-charcoal">
      {label}: <span className="font-bold">{text}</span>
    </p>
  );
}

"use client";

import { useQuery } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { warehouseApi, type Placement } from "@/lib/client-api";

import { formatWarehouseTimestamp } from "./shared";

export function MovementHistory({
  placement,
  onClose,
}: {
  placement: Placement;
  onClose: () => void;
}) {
  const t = useTranslations("warehouse.stock.history");
  const locale = useLocale();
  const movements = useQuery({
    queryKey: ["warehouse-movements", placement.id],
    queryFn: ({ signal }) => warehouseApi.placements.movements(placement.id, signal),
  });

  const rows = movements.data?.ok ? movements.data.data.items : [];

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={t("title")}
      className="fixed inset-0 z-50 grid place-items-center bg-ink/40 p-4"
    >
      <div className="max-h-[80dvh] w-full max-w-2xl overflow-y-auto rounded-xl border border-fog bg-canvas p-6 shadow-floating-modal">
        <div className="flex items-center justify-between gap-2">
          <h3 className="text-lg font-bold">{t("title")}</h3>
          <Button type="button" variant="outline" onClick={onClose} className="h-11 rounded-md">
            {t("close")}
          </Button>
        </div>
        <p className="mt-1 text-sm text-charcoal">
          {t("subtitle", {
            item: placement.item.name,
            shelf: placement.shelf.code,
            quantity: placement.quantity,
          })}
        </p>
        {movements.isPending ? (
          <div className="mt-4 grid gap-2">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : (
          <ul className="mt-4 grid gap-2">
            {rows.map((movement) => (
              <li
                key={movement.id}
                className="grid gap-1 rounded-lg border border-fog p-3 text-sm md:grid-cols-[auto_1fr_auto]"
              >
                <span className="rounded-md bg-cloud px-2 py-0.5 font-bold">
                  {t(`types.${movement.movement_type}`)}
                </span>
                <span className="text-charcoal">
                  {movement.quantity_delta.startsWith("-") ? "" : "+"}
                  {movement.quantity_delta} → {movement.resulting_quantity}
                  {movement.reason ? (
                    <span className="block text-xs text-graphite">{movement.reason}</span>
                  ) : null}
                </span>
                <span className="text-xs text-graphite">
                  {formatWarehouseTimestamp(movement.created_at, locale)}
                </span>
              </li>
            ))}
            {rows.length === 0 ? (
              <li className="p-3 text-center text-graphite">{t("empty")}</li>
            ) : null}
          </ul>
        )}
      </div>
    </div>
  );
}

"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  warehouseApi,
  type ApiError,
  type Placement,
  type WarehouseItem,
} from "@/lib/client-api";

import { warehouseErrorMessage } from "./shared";
import { ItemSearchCombobox } from "./ItemSearchCombobox";
import { MovementHistory } from "./MovementHistory";

type DialogKind = "receive" | "issue" | "adjust";

export function StockView() {
  const t = useTranslations("warehouse.stock");
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [page, setPage] = useState(1);
  const [includeEmpty, setIncludeEmpty] = useState(false);
  const [dialog, setDialog] = useState<{ kind: DialogKind; placement?: Placement } | null>(null);
  const [historyFor, setHistoryFor] = useState<Placement | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const listQuery = useQuery({
    queryKey: ["warehouse-placements", { debounced, page, includeEmpty }],
    queryFn: ({ signal }) =>
      warehouseApi.placements.list(
        { search: debounced || undefined, page, pageSize: 20, includeEmpty },
        signal,
      ),
  });

  const onSearchChange = (value: string) => {
    setSearch(value);
    const timer = setTimeout(() => {
      setDebounced(value);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  };

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["warehouse-placements"] });
    void queryClient.invalidateQueries({ queryKey: ["warehouse-alerts"] });
  };

  const items = listQuery.data?.ok ? listQuery.data.data.items : [];
  const total = listQuery.data?.ok ? listQuery.data.data.total : 0;
  const totalPages = Math.max(1, Math.ceil(total / 20));

  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-center gap-3">
        <Input
          type="search"
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder={t("searchPlaceholder")}
          aria-label={t("searchPlaceholder")}
          className="h-11 w-full max-w-xs rounded-md"
        />
        <Button
          type="button"
          onClick={() => setDialog({ kind: "receive" })}
          className="h-11 rounded-md"
        >
          {t("receiveTitle")}
        </Button>
        <label className="flex h-11 items-center gap-2 text-sm text-charcoal">
          <input
            type="checkbox"
            checked={includeEmpty}
            onChange={(event) => {
              setIncludeEmpty(event.target.checked);
              setPage(1);
            }}
            className="size-4"
          />
          {t("includeEmpty")}
        </label>
      </div>

      {actionError ? (
        <p role="alert" className="text-sm font-bold text-bloom-deep">
          {actionError}
        </p>
      ) : null}

      {dialog ? (
        <MovementDialog
          kind={dialog.kind}
          placement={dialog.placement}
          onClose={() => setDialog(null)}
          onError={setActionError}
        />
      ) : null}

      {listQuery.isPending ? (
        <div className="grid gap-2">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="responsive-table w-full text-sm md:min-w-[44rem]">
            <thead>
              <tr className="border-b border-fog text-charcoal">
                <th scope="col" className="p-3 text-start font-bold">
                  {t("table.item")}
                </th>
                <th scope="col" className="p-3 text-start font-bold">
                  {t("table.shelf")}
                </th>
                <th scope="col" className="p-3 text-start font-bold">
                  {t("table.warehouse")}
                </th>
                <th scope="col" className="p-3 text-start font-bold">
                  {t("table.quantity")}
                </th>
                <th scope="col" className="p-3 text-start font-bold">
                  <span className="sr-only">{t("table.actions")}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {items.map((placement) => (
                <tr key={placement.id} className="border-b border-fog/60">
                  <td data-label={t("table.item")} className="p-3">
                    {placement.item.name}
                    <span className="block text-xs text-graphite">{placement.item.code ?? "—"}</span>
                  </td>
                  <td data-label={t("table.shelf")} className="p-3">
                    {placement.shelf.code}
                  </td>
                  <td data-label={t("table.warehouse")} className="p-3">
                    {placement.warehouse.name}
                  </td>
                  <td data-label={t("table.quantity")} className="p-3">
                    <span className={placement.below_min_threshold ? "font-bold text-bloom-deep" : ""}>
                      {placement.quantity}
                    </span>
                    <span className="ms-1 text-xs text-graphite">{placement.item.unit}</span>
                  </td>
                  <td className="p-3">
                    <div className="flex justify-end gap-1">
                      <button
                        type="button"
                        onClick={() => setDialog({ kind: "issue", placement })}
                        className="flex h-11 items-center rounded-md px-3 text-sm text-charcoal outline-none transition-colors duration-200 hover:bg-cloud focus-visible:ring-2 focus-visible:ring-ring/50"
                      >
                        {t("issueTitle")}
                      </button>
                      <button
                        type="button"
                        onClick={() => setDialog({ kind: "adjust", placement })}
                        className="flex h-11 items-center rounded-md px-3 text-sm text-charcoal outline-none transition-colors duration-200 hover:bg-cloud focus-visible:ring-2 focus-visible:ring-ring/50"
                      >
                        {t("adjustTitle")}
                      </button>
                      <button
                        type="button"
                        onClick={() => setHistoryFor(placement)}
                        className="flex h-11 items-center rounded-md px-3 text-sm text-charcoal outline-none transition-colors duration-200 hover:bg-cloud focus-visible:ring-2 focus-visible:ring-ring/50"
                      >
                        {t("historyTitle")}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {items.length === 0 ? (
                <tr>
                  <td colSpan={5} className="p-6 text-center text-graphite">
                    {t("empty")}
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      )}

      <div className="flex items-center justify-between text-sm text-charcoal">
        <span>{t("pageIndicator", { page, totalPages })}</span>
        <div className="flex gap-1">
          <Button
            type="button"
            variant="outline"
            disabled={page <= 1}
            onClick={() => setPage((current) => current - 1)}
            className="h-11 rounded-md"
          >
            {t("previousPage")}
          </Button>
          <Button
            type="button"
            variant="outline"
            disabled={page >= totalPages}
            onClick={() => setPage((current) => current + 1)}
            className="h-11 rounded-md"
          >
            {t("nextPage")}
          </Button>
        </div>
      </div>

      {historyFor ? (
        <MovementHistory
          placement={historyFor}
          onClose={() => {
            setHistoryFor(null);
            invalidate();
          }}
        />
      ) : null}
    </div>
  );
}

function MovementDialog({
  kind,
  placement,
  onClose,
  onError,
}: {
  kind: DialogKind;
  placement?: Placement;
  onClose: () => void;
  onError: (message: string) => void;
}) {
  const t = useTranslations("warehouse.stock");
  const queryClient = useQueryClient();
  const [selectedItem, setSelectedItem] = useState<WarehouseItem | null>(null);
  const [shelfId, setShelfId] = useState("");
  const [quantity, setQuantity] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const shelvesQuery = useQuery({
    queryKey: ["warehouse-warehouses-for-picker"],
    queryFn: ({ signal }) => warehouseApi.warehouses.list({ pageSize: 100 }, signal),
  });
  const [warehouseId, setWarehouseId] = useState("");
  const shelves = useQuery({
    queryKey: ["warehouse-shelves", warehouseId],
    queryFn: ({ signal }) => warehouseApi.warehouses.shelves(warehouseId, signal),
    enabled: warehouseId !== "" && kind === "receive",
  });

  const submit = useMutation({
    mutationFn: () => {
      if (kind === "receive") {
        return warehouseApi.placements.receive({
          item_id: selectedItem?.id,
          shelf_id: shelfId,
          quantity,
          reason: reason || null,
        });
      }
      if (kind === "issue") {
        return warehouseApi.placements.issue({
          placement_id: placement?.id,
          quantity,
          reason: reason || null,
        });
      }
      return warehouseApi.placements.adjust({
        placement_id: placement?.id,
        quantity,
        reason: reason || null,
      });
    },
    onSuccess: () => {
      onError("");
      void queryClient.invalidateQueries({ queryKey: ["warehouse-placements"] });
      void queryClient.invalidateQueries({ queryKey: ["warehouse-alerts"] });
      onClose();
    },
    onError: (mutationError: ApiError) => setError(warehouseErrorMessage(t, mutationError)),
  });

  return (
    <form
      className="grid gap-4 rounded-xl border border-fog bg-canvas p-6"
      onSubmit={(event) => {
        event.preventDefault();
        setError(null);
        submit.mutate();
      }}
    >
      <h3 className="text-lg font-bold">{t(`${kind}Title`)}</h3>
      {error ? (
        <p role="alert" className="text-sm font-bold text-bloom-deep">
          {error}
        </p>
      ) : null}
      {kind === "receive" ? (
        <>
          <div className="grid gap-2">
            <Label htmlFor="movement-item">{t("dialog.item")}</Label>
            <ItemSearchCombobox
              selected={selectedItem}
              onSelect={(item) => setSelectedItem(item)}
              onClear={() => setSelectedItem(null)}
              invalid={error !== null && selectedItem === null}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="movement-warehouse">{t("dialog.warehouse")}</Label>
            <select
              id="movement-warehouse"
              required
              value={warehouseId}
              onChange={(event) => setWarehouseId(event.target.value)}
              className="h-11 rounded-md border border-steel bg-canvas px-3 text-sm"
            >
              <option value="">{t("dialog.warehousePlaceholder")}</option>
              {(shelvesQuery.data?.ok ? shelvesQuery.data.data.items : []).map((warehouse) => (
                <option key={warehouse.id} value={warehouse.id}>
                  {warehouse.name} · {warehouse.code}
                </option>
              ))}
            </select>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="movement-shelf">{t("dialog.shelf")}</Label>
            <select
              id="movement-shelf"
              required
              value={shelfId}
              onChange={(event) => setShelfId(event.target.value)}
              className="h-11 rounded-md border border-steel bg-canvas px-3 text-sm"
            >
              <option value="">{t("dialog.shelfPlaceholder")}</option>
              {(shelves.data?.ok ? shelves.data.data.items : []).map((shelf) => (
                <option key={shelf.id} value={shelf.id}>
                  {shelf.code}
                  {shelf.name ? ` · ${shelf.name}` : ""}
                </option>
              ))}
            </select>
          </div>
        </>
      ) : (
        <p className="text-sm text-charcoal">
          {t("dialog.target", {
            item: placement?.item.name ?? "",
            shelf: placement?.shelf.code ?? "",
            quantity: placement?.quantity ?? "",
          })}
        </p>
      )}
      <div className="grid gap-2">
        <Label htmlFor="movement-quantity">
          {kind === "adjust" ? t("dialog.countedQuantity") : t("dialog.quantity")}
        </Label>
        <Input
          id="movement-quantity"
          required
          inputMode="decimal"
          value={quantity}
          onChange={(event) => setQuantity(event.target.value)}
          className="h-11 rounded-md"
        />
      </div>
      <div className="grid gap-2">
        <Label htmlFor="movement-reason">{t("dialog.reason")}</Label>
        <Input
          id="movement-reason"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          className="h-11 rounded-md"
        />
      </div>
      <div className="flex gap-2">
        <Button type="submit" disabled={submit.isPending} className="h-11 rounded-md">
          {submit.isPending ? t("dialog.saving") : t("dialog.submit")}
        </Button>
        <Button type="button" variant="outline" onClick={onClose} className="h-11 rounded-md">
          {t("dialog.cancel")}
        </Button>
      </div>
    </form>
  );
}

"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  warehouseApi,
  type ApiError,
  type WarehouseItem,
} from "@/lib/client-api";
import { WarehouseItemInputSchema } from "@/lib/schemas";

import { warehouseErrorMessage } from "./shared";

type FormState = {
  id?: string;
  version?: number;
  name: string;
  name_fa: string;
  code: string;
  unit: string;
  min_quantity: string;
  description: string;
};

const EMPTY_FORM: FormState = {
  name: "",
  name_fa: "",
  code: "",
  unit: "ad",
  min_quantity: "0",
  description: "",
};

export function CatalogView() {
  const t = useTranslations("warehouse.catalog");
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [page, setPage] = useState(1);
  const [form, setForm] = useState<FormState | null>(null);
  const [retireTarget, setRetireTarget] = useState<WarehouseItem | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const listQuery = useQuery({
    queryKey: ["warehouse-items", { debounced, page }],
    queryFn: ({ signal }) =>
      warehouseApi.items.list({ search: debounced || undefined, page, pageSize: 20 }, signal),
  });

  const searchDebounce = useRef<number | null>(null);

  const onSearchChange = (value: string) => {
    setSearch(value);
    if (searchDebounce.current !== null) {
      window.clearTimeout(searchDebounce.current);
    }
    searchDebounce.current = window.setTimeout(() => {
      setDebounced(value);
      setPage(1);
    }, 300);
  };

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["warehouse-items"] });
  };

  const save = useMutation({
    mutationFn: (state: FormState) => {
      const parsed = WarehouseItemInputSchema.safeParse({
        name: state.name,
        name_fa: state.name_fa,
        code: state.code || null,
        unit: state.unit,
        min_quantity: state.min_quantity,
        description: state.description || null,
      });
      if (!parsed.success) {
        const message = parsed.error.issues[0]?.message ?? "warehouse.errors.generic";
        throw Object.assign(new Error(message), { i18nKey: true });
      }
      return state.id
        ? warehouseApi.items.update(state.id, { ...parsed.data, version: state.version })
        : warehouseApi.items.create(parsed.data);
    },
    onSuccess: () => {
      setFormError(null);
      setForm(null);
      invalidate();
    },
    onError: (error: ApiError & { i18nKey?: boolean }) =>
      setFormError(
        error.i18nKey && t.has(error.message)
          ? t(error.message)
          : warehouseErrorMessage(t, error),
      ),
  });

  const retire = useMutation({
    mutationFn: (item: WarehouseItem) => warehouseApi.items.retire(item.id, item.version),
    onSuccess: () => {
      setActionError(null);
      setRetireTarget(null);
      invalidate();
    },
    onError: (error: ApiError) => setActionError(warehouseErrorMessage(t, error)),
  });

  const items = listQuery.data?.ok ? listQuery.data.data.items : [];
  const total = listQuery.data?.ok ? listQuery.data.data.total : 0;
  const totalPages = Math.max(1, Math.ceil(total / 20));

  return (
    <div className="grid gap-6">
      {form ? (
        <form
          className="grid gap-4 rounded-xl border border-fog bg-canvas p-6"
          onSubmit={(event) => {
            event.preventDefault();
            setFormError(null);
            save.mutate(form);
          }}
        >
          <h3 className="text-lg font-bold">{form.id ? t("editTitle") : t("createTitle")}</h3>
          {formError ? (
            <p role="alert" className="text-sm font-bold text-bloom-deep">
              {formError}
            </p>
          ) : null}
          <div className="grid gap-4 md:grid-cols-2">
            <div className="grid gap-2">
              <Label htmlFor="item-name">{t("form.name")}</Label>
              <Input
                id="item-name"
                required
                value={form.name}
                onChange={(event) => setForm({ ...form, name: event.target.value })}
                className="h-11 rounded-md"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="item-name-fa">{t("form.nameFa")}</Label>
              <Input
                id="item-name-fa"
                required
                value={form.name_fa}
                onChange={(event) => setForm({ ...form, name_fa: event.target.value })}
                className="h-11 rounded-md"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="item-code">{t("form.code")}</Label>
              <Input
                id="item-code"
                value={form.code}
                onChange={(event) => setForm({ ...form, code: event.target.value })}
                className="h-11 rounded-md"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="item-unit">{t("form.unit")}</Label>
              <Input
                id="item-unit"
                required
                value={form.unit}
                onChange={(event) => setForm({ ...form, unit: event.target.value })}
                className="h-11 rounded-md"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="item-min">{t("form.minQuantity")}</Label>
              <Input
                id="item-min"
                inputMode="decimal"
                value={form.min_quantity}
                onChange={(event) => setForm({ ...form, min_quantity: event.target.value })}
                className="h-11 rounded-md"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="item-description">{t("form.description")}</Label>
              <Input
                id="item-description"
                value={form.description}
                onChange={(event) => setForm({ ...form, description: event.target.value })}
                className="h-11 rounded-md"
              />
            </div>
          </div>
          <div className="flex gap-2">
            <Button type="submit" disabled={save.isPending} className="h-11 rounded-md">
              {save.isPending ? t("form.saving") : t("form.save")}
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setForm(null);
                setFormError(null);
              }}
              className="h-11 rounded-md"
            >
              {t("form.cancel")}
            </Button>
          </div>
        </form>
      ) : (
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
            onClick={() => setForm({ ...EMPTY_FORM })}
            className="h-11 rounded-md"
          >
            {t("createTitle")}
          </Button>
        </div>
      )}

      {actionError ? (
        <p role="alert" className="text-sm font-bold text-bloom-deep">
          {actionError}
        </p>
      ) : null}

      {listQuery.isPending ? (
        <div className="grid gap-2">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="responsive-table w-full text-sm md:min-w-[40rem]">
            <thead>
              <tr className="border-b border-fog text-start text-charcoal">
                <th scope="col" className="p-3 text-start font-bold">
                  {t("table.name")}
                </th>
                <th scope="col" className="p-3 text-start font-bold">
                  {t("table.code")}
                </th>
                <th scope="col" className="p-3 text-start font-bold">
                  {t("table.unit")}
                </th>
                <th scope="col" className="p-3 text-start font-bold">
                  {t("table.minQuantity")}
                </th>
                <th scope="col" className="p-3 text-start font-bold">
                  <span className="sr-only">{t("table.actions")}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id} className="border-b border-fog/60">
                  <td data-label={t("table.name")} className="p-3">
                    {item.name}
                    <span className="block text-xs text-graphite">{item.name_fa}</span>
                  </td>
                  <td data-label={t("table.code")} className="p-3">
                    {item.code ?? "—"}
                  </td>
                  <td data-label={t("table.unit")} className="p-3">
                    {item.unit}
                  </td>
                  <td data-label={t("table.minQuantity")} className="p-3">
                    {item.min_quantity}
                  </td>
                  <td className="p-3">
                    <div className="flex justify-end gap-1">
                      <button
                        type="button"
                        onClick={() =>
                          setForm({
                            id: item.id,
                            version: item.version,
                            name: item.name,
                            name_fa: item.name_fa,
                            code: item.code ?? "",
                            unit: item.unit,
                            min_quantity: item.min_quantity,
                            description: item.description ?? "",
                          })
                        }
                        className="flex h-11 items-center rounded-md px-3 text-sm text-charcoal outline-none transition-colors duration-200 hover:bg-cloud hover:text-ink focus-visible:ring-2 focus-visible:ring-ring/50"
                      >
                        {t("table.edit")}
                      </button>
                      <button
                        type="button"
                        onClick={() => setRetireTarget(item)}
                        className="flex h-11 items-center rounded-md px-3 text-sm text-bloom-deep outline-none transition-colors duration-200 hover:bg-cloud focus-visible:ring-2 focus-visible:ring-ring/50"
                      >
                        {t("table.retire")}
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
        <span>
          {t("pageIndicator", { page, totalPages })}
        </span>
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

      {retireTarget ? (
        <div
          role="alertdialog"
          aria-modal="true"
          aria-label={t("retireTitle")}
          className="fixed inset-0 z-50 grid place-items-center bg-ink/40 p-4"
        >
          <div className="w-full max-w-md rounded-xl border border-fog bg-canvas p-6 shadow-floating-modal">
            <h3 className="text-lg font-bold">{t("retireTitle")}</h3>
            <p className="mt-2 text-sm text-charcoal">
              {t("retireDescription", { name: retireTarget.name })}
            </p>
            <div className="mt-4 flex gap-2">
              <Button
                type="button"
                onClick={() => retire.mutate(retireTarget)}
                disabled={retire.isPending}
                className="h-11 rounded-md"
              >
                {retire.isPending ? t("form.saving") : t("table.retire")}
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => setRetireTarget(null)}
                className="h-11 rounded-md"
              >
                {t("form.cancel")}
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

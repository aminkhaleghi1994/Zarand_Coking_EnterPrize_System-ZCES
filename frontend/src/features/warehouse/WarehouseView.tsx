"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { orgApi, warehouseApi, type ApiError, type Warehouse } from "@/lib/client-api";

import { warehouseErrorMessage } from "./shared";

type FormState = {
  kind: "create" | "edit";
  warehouse?: Warehouse;
  workplace_id: string;
  code: string;
  name: string;
  name_fa: string;
};

export function WarehouseView() {
  const t = useTranslations("warehouse.warehouses");
  const queryClient = useQueryClient();
  const [form, setForm] = useState<FormState | null>(null);
  const [shelvesFor, setShelvesFor] = useState<Warehouse | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const listQuery = useQuery({
    queryKey: ["warehouse-warehouses"],
    queryFn: ({ signal }) => warehouseApi.warehouses.list({ pageSize: 100 }, signal),
  });
  const workplacesQuery = useQuery({
    queryKey: ["workplaces-picker"],
    queryFn: ({ signal }) => orgApi.workplaces(signal),
  });

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["warehouse-warehouses"] });
    void queryClient.invalidateQueries({ queryKey: ["warehouse-shelves"] });
    void queryClient.invalidateQueries({ queryKey: ["warehouse-placements"] });
  };

  const save = useMutation({
    mutationFn: (state: FormState) => {
      const payload = { code: state.code, name: state.name, name_fa: state.name_fa };
      if (state.kind === "create") {
        return warehouseApi.warehouses.create({ ...payload, workplace_id: state.workplace_id });
      }
      if (!state.warehouse) {
        throw new Error("Missing warehouse for edit");
      }
      return warehouseApi.warehouses.update(state.warehouse.id, {
        ...payload,
        version: state.warehouse.version,
      });
    },
    onSuccess: () => {
      setFormError(null);
      setForm(null);
      invalidate();
    },
    onError: (error: ApiError) => setFormError(warehouseErrorMessage(t, error)),
  });

  const retire = useMutation({
    mutationFn: (warehouse: Warehouse) =>
      warehouseApi.warehouses.retire(warehouse.id, warehouse.version),
    onSuccess: () => {
      setActionError(null);
      invalidate();
    },
    onError: (error: ApiError) => setActionError(warehouseErrorMessage(t, error)),
  });

  const warehouses = listQuery.data?.ok ? listQuery.data.data.items : [];
  const workplaces = workplacesQuery.data?.ok ? workplacesQuery.data.data.items : [];

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
          <h3 className="text-lg font-bold">
            {form.kind === "create" ? t("createTitle") : t("editTitle")}
          </h3>
          {formError ? (
            <p role="alert" className="text-sm font-bold text-bloom-deep">
              {formError}
            </p>
          ) : null}
          <div className="grid gap-4 md:grid-cols-2">
            {form.kind === "create" ? (
              <div className="grid gap-2">
                <Label htmlFor="wh-workplace">{t("form.workplace")}</Label>
                <select
                  id="wh-workplace"
                  required
                  value={form.workplace_id}
                  onChange={(event) => setForm({ ...form, workplace_id: event.target.value })}
                  className="h-11 rounded-md border border-steel bg-canvas px-3 text-sm"
                >
                  <option value="">{t("form.workplacePlaceholder")}</option>
                  {workplaces.map((workplace) => (
                    <option key={workplace.id} value={workplace.id}>
                      {workplace.name} · {workplace.code}
                    </option>
                  ))}
                </select>
              </div>
            ) : null}
            <div className="grid gap-2">
              <Label htmlFor="wh-code">{t("form.code")}</Label>
              <Input
                id="wh-code"
                required
                value={form.code}
                onChange={(event) => setForm({ ...form, code: event.target.value })}
                className="h-11 rounded-md"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="wh-name">{t("form.name")}</Label>
              <Input
                id="wh-name"
                required
                value={form.name}
                onChange={(event) => setForm({ ...form, name: event.target.value })}
                className="h-11 rounded-md"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="wh-name-fa">{t("form.nameFa")}</Label>
              <Input
                id="wh-name-fa"
                required
                value={form.name_fa}
                onChange={(event) => setForm({ ...form, name_fa: event.target.value })}
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
          <Button
            type="button"
            onClick={() =>
              setForm({ kind: "create", workplace_id: "", code: "", name: "", name_fa: "" })
            }
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
        </div>
      ) : (
        <div className="grid gap-3">
          {warehouses.map((warehouse) => (
            <div
              key={warehouse.id}
              className="grid gap-3 rounded-xl border border-fog bg-canvas p-4 md:grid-cols-[1fr_auto]"
            >
              <div className="grid gap-1">
                <p className="font-bold">
                  {warehouse.name}
                  <span className="ms-2 text-xs text-graphite">{warehouse.code}</span>
                </p>
                <p className="text-sm text-charcoal">{warehouse.name_fa}</p>
                {shelvesFor?.id === warehouse.id ? (
                  <ShelvesPanel warehouse={warehouse} onError={setActionError} />
                ) : null}
              </div>
              <div className="flex items-start gap-1">
                <button
                  type="button"
                  onClick={() => setShelvesFor(shelvesFor?.id === warehouse.id ? null : warehouse)}
                  className="flex h-11 items-center rounded-md px-3 text-sm text-charcoal outline-none transition-colors duration-200 hover:bg-cloud focus-visible:ring-2 focus-visible:ring-ring/50"
                >
                  {t("manageShelves")}
                </button>
                <button
                  type="button"
                  onClick={() =>
                    setForm({
                      kind: "edit",
                      warehouse,
                      workplace_id: warehouse.workplace_id,
                      code: warehouse.code,
                      name: warehouse.name,
                      name_fa: warehouse.name_fa,
                    })
                  }
                  className="flex h-11 items-center rounded-md px-3 text-sm text-charcoal outline-none transition-colors duration-200 hover:bg-cloud hover:text-ink focus-visible:ring-2 focus-visible:ring-ring/50"
                >
                  {t("table.edit")}
                </button>
                <button
                  type="button"
                  onClick={() => retire.mutate(warehouse)}
                  disabled={retire.isPending}
                  className="flex h-11 items-center rounded-md px-3 text-sm text-bloom-deep outline-none transition-colors duration-200 hover:bg-cloud focus-visible:ring-2 focus-visible:ring-ring/50"
                >
                  {t("table.retire")}
                </button>
              </div>
            </div>
          ))}
          {warehouses.length === 0 ? (
            <p className="p-6 text-center text-graphite">{t("empty")}</p>
          ) : null}
        </div>
      )}
    </div>
  );
}

function ShelvesPanel({
  warehouse,
  onError,
}: {
  warehouse: Warehouse;
  onError: (message: string) => void;
}) {
  const t = useTranslations("warehouse.warehouses.shelves");
  const queryClient = useQueryClient();
  const [newCode, setNewCode] = useState("");
  const [addError, setAddError] = useState<string | null>(null);

  const shelvesQuery = useQuery({
    queryKey: ["warehouse-shelves", warehouse.id],
    queryFn: ({ signal }) => warehouseApi.warehouses.shelves(warehouse.id, signal),
  });

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["warehouse-shelves", warehouse.id] });
    void queryClient.invalidateQueries({ queryKey: ["warehouse-placements"] });
  };

  const create = useMutation({
    mutationFn: () => warehouseApi.warehouses.createShelf(warehouse.id, { code: newCode }),
    onSuccess: () => {
      setAddError(null);
      setNewCode("");
      invalidate();
    },
    onError: (error: ApiError) => setAddError(warehouseErrorMessage(t, error)),
  });

  const retire = useMutation({
    mutationFn: (input: { shelfId: string; version: number }) =>
      warehouseApi.warehouses.retireShelf(input.shelfId, input.version),
    onSuccess: () => {
      onError("");
      invalidate();
    },
    onError: (error: ApiError) => onError(warehouseErrorMessage(t, error)),
  });

  const shelves = shelvesQuery.data?.ok ? shelvesQuery.data.data.items : [];

  return (
    <div className="mt-2 grid gap-2 rounded-lg border border-fog bg-cloud/50 p-3">
      <p className="text-xs font-bold uppercase tracking-widest text-graphite">
        {t("sectionTitle")}
      </p>
      {shelves.map((shelf) => (
        <div key={shelf.id} className="flex items-center justify-between gap-2 text-sm">
          <span>
            {shelf.code}
            {shelf.name ? <span className="text-graphite"> · {shelf.name}</span> : null}
          </span>
          <button
            type="button"
            onClick={() => retire.mutate({ shelfId: shelf.id, version: shelf.version })}
            disabled={retire.isPending}
            className="flex h-9 items-center rounded-md px-2 text-xs text-bloom-deep outline-none transition-colors duration-200 hover:bg-cloud focus-visible:ring-2 focus-visible:ring-ring/50"
          >
            {t("retire")}
          </button>
        </div>
      ))}
      {shelves.length === 0 ? <p className="text-sm text-graphite">{t("empty")}</p> : null}
      <form
        className="flex gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          create.mutate();
        }}
      >
        <Input
          required
          value={newCode}
          onChange={(event) => setNewCode(event.target.value)}
          placeholder={t("codePlaceholder")}
          aria-label={t("codePlaceholder")}
          className="h-11 max-w-40 rounded-md"
        />
        <Button type="submit" disabled={create.isPending} className="h-11 rounded-md">
          {t("add")}
        </Button>
      </form>
      {addError ? (
        <p role="alert" className="text-sm font-bold text-bloom-deep">
          {addError}
        </p>
      ) : null}
    </div>
  );
}

"use client";

import { useMutation } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { requestApi, type ApiError, type WarehouseItem } from "@/lib/client-api";
import { RequestInputSchema } from "@/lib/schemas";

import { ItemSearchCombobox } from "@/features/warehouse/ItemSearchCombobox";
import { warehouseErrorMessage } from "@/features/warehouse/shared";

type LineDraft = {
  key: string;
  item: WarehouseItem | null;
  quantity: string;
  note: string;
};

export function RequestForm({ onCreated }: { onCreated: () => void }) {
  const t = useTranslations("requests.form");
  const [purpose, setPurpose] = useState("");
  const [lines, setLines] = useState<LineDraft[]>([
    { key: crypto.randomUUID(), item: null, quantity: "", note: "" },
  ]);
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: (payload: unknown) => requestApi.create(payload),
    onSuccess: () => {
      setError(null);
      setPurpose("");
      setLines([{ key: crypto.randomUUID(), item: null, quantity: "", note: "" }]);
      onCreated();
    },
    onError: (mutationError: ApiError) => setError(warehouseErrorMessage(t, mutationError)),
  });

  const updateLine = (key: string, patch: Partial<LineDraft>) => {
    setLines((current) => current.map((line) => (line.key === key ? { ...line, ...patch } : line)));
  };

  const submit = () => {
    setError(null);
    const parsed = RequestInputSchema.safeParse({
      purpose_description: purpose,
      lines: lines.map((line) => ({
        item_id: line.item?.id ?? "",
        quantity: line.quantity,
        note: line.note || null,
      })),
    });
    if (!parsed.success) {
      const issue = parsed.error.issues[0];
      const key = issue?.message ?? "requests.errors.generic";
      setError(t.has(key) ? t(key) : t("errors.generic"));
      return;
    }
    create.mutate(parsed.data);
  };

  return (
    <form
      className="grid gap-4 rounded-xl border border-fog bg-canvas p-6"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <h3 className="text-lg font-bold">{t("title")}</h3>
      {error ? (
        <p role="alert" className="text-sm font-bold text-bloom-deep">
          {error}
        </p>
      ) : null}
      <div className="grid gap-2">
        <Label htmlFor="request-purpose">{t("purpose")}</Label>
        <textarea
          id="request-purpose"
          required
          value={purpose}
          onChange={(event) => setPurpose(event.target.value)}
          placeholder={t("purposePlaceholder")}
          rows={2}
          className="rounded-md border border-steel bg-canvas px-3 py-2 text-sm outline-none transition-colors duration-200 focus-visible:ring-2 focus-visible:ring-ring/50"
        />
      </div>
      <div className="grid gap-3">
        <p className="text-xs font-bold uppercase tracking-widest text-graphite">{t("lines")}</p>
        {lines.map((line, index) => (
          <div key={line.key} className="grid gap-2 rounded-lg border border-fog p-3">
            <div className="grid gap-2 md:grid-cols-[1fr_10rem_auto]">
              <div className="grid gap-1">
                <Label htmlFor={`line-item-${index}`}>{t("item")}</Label>
                <ItemSearchCombobox
                  selected={line.item}
                  onSelect={(item) => updateLine(line.key, { item })}
                  onClear={() => updateLine(line.key, { item: null })}
                />
              </div>
              <div className="grid gap-1">
                <Label htmlFor={`line-qty-${index}`}>{t("quantity")}</Label>
                <Input
                  id={`line-qty-${index}`}
                  required
                  inputMode="decimal"
                  value={line.quantity}
                  onChange={(event) => updateLine(line.key, { quantity: event.target.value })}
                  className="h-11 rounded-md"
                />
              </div>
              <div className="flex items-end">
                <Button
                  type="button"
                  variant="outline"
                  disabled={lines.length === 1}
                  onClick={() => setLines((current) => current.filter((l) => l.key !== line.key))}
                  className="h-11 rounded-md"
                >
                  {t("removeLine")}
                </Button>
              </div>
            </div>
            <Input
              value={line.note}
              onChange={(event) => updateLine(line.key, { note: event.target.value })}
              placeholder={t("lineNote")}
              aria-label={t("lineNote")}
              className="h-11 rounded-md"
            />
          </div>
        ))}
        <Button
          type="button"
          variant="outline"
          onClick={() =>
            setLines((current) => [
              ...current,
              { key: crypto.randomUUID(), item: null, quantity: "", note: "" },
            ])
          }
          className="h-11 rounded-md"
        >
          {t("addLine")}
        </Button>
      </div>
      <Button type="submit" disabled={create.isPending} className="h-11 rounded-md">
        {create.isPending ? t("submitting") : t("submit")}
      </Button>
    </form>
  );
}

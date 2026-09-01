"use client";

import { useMutation } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { assetApi, type ApiError, type AssetRecord } from "@/lib/client-api";
import { AssetInputSchema } from "@/lib/schemas";
import { warehouseErrorMessage } from "@/features/warehouse/shared";

type AssetFormProps = {
  asset?: AssetRecord;
  onCancel: () => void;
  onSaved: () => void;
};

type CreatePayload = {
  name: string;
  name_fa: string;
  serial: string;
  description: string | null;
};

type EditPayload = {
  name: string;
  name_fa: string;
  description: string | null;
  version: number;
};

export function AssetForm({ asset, onCancel, onSaved }: AssetFormProps) {
  const t = useTranslations("assets.form");
  const tRoot = useTranslations("assets");
  const editing = Boolean(asset);
  const [name, setName] = useState(asset?.name ?? "");
  const [nameFa, setNameFa] = useState(asset?.name_fa ?? "");
  const [serial, setSerial] = useState(asset?.serial ?? "");
  const [description, setDescription] = useState(asset?.description ?? "");
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: (payload: CreatePayload | EditPayload) =>
      editing ? assetApi.update(asset!.id, payload) : assetApi.create(payload),
    onSuccess: () => {
      setError(null);
      onSaved();
    },
    onError: (mutationError: ApiError) => setError(warehouseErrorMessage(tRoot, mutationError)),
  });

  const submit = () => {
    setError(null);
    const parsed = AssetInputSchema.safeParse({
      name,
      name_fa: nameFa,
      serial,
      description: description || null,
    });
    if (!parsed.success) {
      const key = parsed.error.issues[0]?.message ?? "assets.errors.generic";
      setError(tRoot.has(key) ? tRoot(key) : tRoot("errors.generic"));
      return;
    }
    const payload: CreatePayload | EditPayload = editing
      ? {
          name: parsed.data.name,
          name_fa: parsed.data.name_fa,
          description: parsed.data.description ?? null,
          version: asset!.version,
        }
      : {
          name: parsed.data.name,
          name_fa: parsed.data.name_fa,
          serial: parsed.data.serial,
          description: parsed.data.description ?? null,
        };
    save.mutate(payload);
  };

  return (
    <form
      className="grid gap-4 rounded-xl border border-fog bg-canvas p-6"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <h3 className="text-lg font-bold">{editing ? t("editTitle") : t("createTitle")}</h3>
      {error ? (
        <p role="alert" className="text-sm font-bold text-bloom-deep">
          {error}
        </p>
      ) : null}
      <div className="grid gap-4 md:grid-cols-2">
        <div className="grid gap-2">
          <Label htmlFor="asset-name">{t("name")}</Label>
          <Input
            id="asset-name"
            required
            value={name}
            onChange={(event) => setName(event.target.value)}
            className="h-11 rounded-md"
          />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="asset-name-fa">{t("nameFa")}</Label>
          <Input
            id="asset-name-fa"
            required
            dir="rtl"
            value={nameFa}
            onChange={(event) => setNameFa(event.target.value)}
            className="h-11 rounded-md"
          />
        </div>
      </div>
      <div className="grid gap-2">
        <Label htmlFor="asset-serial">{t("serial")}</Label>
        <Input
          id="asset-serial"
          required
          dir="ltr"
          value={serial}
          onChange={(event) => setSerial(event.target.value)}
          disabled={editing}
          aria-describedby={editing ? "asset-serial-hint" : undefined}
          className="h-11 rounded-md disabled:cursor-not-allowed disabled:bg-cloud disabled:text-graphite"
        />
        {editing ? (
          <p id="asset-serial-hint" className="text-xs text-graphite">
            {t("serialHint")}
          </p>
        ) : null}
      </div>
      <div className="grid gap-2">
        <Label htmlFor="asset-description">{t("description")}</Label>
        <textarea
          id="asset-description"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          rows={2}
          className="rounded-md border border-steel bg-canvas px-3 py-2 text-sm outline-none transition-colors duration-200 focus-visible:ring-2 focus-visible:ring-ring/50"
        />
      </div>
      <div className="flex gap-2">
        <Button type="submit" disabled={save.isPending} className="h-11 rounded-md">
          {save.isPending
            ? editing
              ? t("saving")
              : t("submitting")
            : editing
              ? t("save")
              : t("submit")}
        </Button>
        <Button type="button" variant="outline" onClick={onCancel} className="h-11 rounded-md">
          {t("cancel")}
        </Button>
      </div>
    </form>
  );
}

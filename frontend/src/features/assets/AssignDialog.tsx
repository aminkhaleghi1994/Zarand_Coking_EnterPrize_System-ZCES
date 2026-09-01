"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { assetApi, employeeApi, type ApiError, type AssetRecord } from "@/lib/client-api";
import { AssetAssignInputSchema, type AssetAssignInput } from "@/lib/schemas";
import { cn } from "@/lib/utils";
import { warehouseErrorMessage } from "@/features/warehouse/shared";

type AssignDialogProps = {
  asset: AssetRecord;
  onClose: () => void;
  onAssigned: () => void;
};

export function AssignDialog({ asset, onClose, onAssigned }: AssignDialogProps) {
  const t = useTranslations("assets.assign");
  const tRoot = useTranslations("assets");
  const [targetType, setTargetType] = useState<"employee" | "location">("employee");
  const [employeeId, setEmployeeId] = useState("");
  const [employeeSearch, setEmployeeSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [location, setLocation] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);

  const employeesQuery = useQuery({
    queryKey: ["assign-employees", debouncedSearch],
    queryFn: ({ signal }) =>
      employeeApi.list(
        { search: debouncedSearch || undefined, status: "active", pageSize: 50 },
        signal,
      ),
  });
  const employees = employeesQuery.data?.ok ? employeesQuery.data.data.items : [];

  const assign = useMutation({
    mutationFn: (payload: AssetAssignInput) =>
      assetApi.assign(asset.id, { ...payload, version: asset.version }),
    onSuccess: () => {
      setError(null);
      onAssigned();
      onClose();
    },
    onError: (mutationError: ApiError) => setError(warehouseErrorMessage(tRoot, mutationError)),
  });

  const onSearchChange = (value: string) => {
    setEmployeeSearch(value);
    window.clearTimeout(
      (window as unknown as { __assignSearchTimer?: number }).__assignSearchTimer,
    );
    (window as unknown as { __assignSearchTimer?: number }).__assignSearchTimer =
      window.setTimeout(() => setDebouncedSearch(value), 300);
  };

  const submit = () => {
    setError(null);
    const parsed = AssetAssignInputSchema.safeParse({
      target_type: targetType,
      employee_id: targetType === "employee" ? employeeId || null : null,
      location: targetType === "location" ? location || null : null,
      note: note || null,
    });
    if (!parsed.success) {
      const key = parsed.error.issues[0]?.message ?? "assets.errors.generic";
      setError(tRoot.has(key) ? tRoot(key) : tRoot("errors.generic"));
      return;
    }
    assign.mutate(parsed.data);
  };

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center p-4">
      <div
        role="presentation"
        onClick={onClose}
        className="absolute inset-0 bg-black/40 motion-safe:animate-in motion-safe:fade-in-0 motion-safe:duration-200"
      />
      <form
        role="dialog"
        aria-modal="true"
        aria-label={t("title")}
        className="relative grid max-h-[90vh] w-full max-w-md gap-4 overflow-y-auto rounded-xl border border-fog bg-canvas p-6 shadow-floating-modal"
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
      >
        <h3 className="text-lg font-bold">{t("title")}</h3>
        <p className="text-sm text-charcoal" dir="ltr">
          {asset.name} · {asset.serial}
        </p>
        {error ? (
          <p role="alert" className="text-sm font-bold text-bloom-deep">
            {error}
          </p>
        ) : null}

        <fieldset className="grid gap-2">
          <legend className="mb-1 text-xs font-bold uppercase tracking-widest text-graphite">
            {t("targetType")}
          </legend>
          <div className="flex gap-2">
            {(["employee", "location"] as const).map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => setTargetType(value)}
                aria-pressed={targetType === value}
                className={cn(
                  "flex h-11 flex-1 items-center justify-center rounded-md border px-4 text-sm outline-none transition-colors duration-200 focus-visible:ring-2 focus-visible:ring-ring/50",
                  targetType === value
                    ? "border-brand bg-brand-soft font-bold text-brand-deep dark:text-brand-bright"
                    : "border-fog text-charcoal hover:bg-cloud",
                )}
              >
                {value === "employee" ? t("targetEmployee") : t("targetLocation")}
              </button>
            ))}
          </div>
        </fieldset>

        {targetType === "employee" ? (
          <div className="grid gap-2">
            <Label htmlFor="assign-employee-search">{t("employeeSearchLabel")}</Label>
            <Input
              id="assign-employee-search"
              type="search"
              value={employeeSearch}
              onChange={(event) => onSearchChange(event.target.value)}
              className="h-11 rounded-md"
            />
            <Label htmlFor="assign-employee">{t("targetEmployee")}</Label>
            <select
              id="assign-employee"
              required
              value={employeeId}
              onChange={(event) => setEmployeeId(event.target.value)}
              className="h-11 rounded-md border border-steel bg-canvas px-3 text-sm"
            >
              <option value="">{t("employeePlaceholder")}</option>
              {employees.map((employee) => (
                <option key={employee.id} value={employee.id}>
                  {employee.first_name} {employee.last_name} · {employee.personnel_code} ·{" "}
                  {employee.workplace_name}
                </option>
              ))}
            </select>
          </div>
        ) : (
          <div className="grid gap-2">
            <Label htmlFor="assign-location">{t("location")}</Label>
            <Input
              id="assign-location"
              required
              value={location}
              onChange={(event) => setLocation(event.target.value)}
              placeholder={t("locationPlaceholder")}
              className="h-11 rounded-md"
            />
          </div>
        )}

        <div className="grid gap-2">
          <Label htmlFor="assign-note">{t("note")}</Label>
          <Input
            id="assign-note"
            value={note}
            onChange={(event) => setNote(event.target.value)}
            className="h-11 rounded-md"
          />
        </div>

        <div className="flex gap-2">
          <Button type="submit" disabled={assign.isPending} className="h-11 rounded-md">
            {assign.isPending ? t("submitting") : t("submit")}
          </Button>
          <Button type="button" variant="outline" onClick={onClose} className="h-11 rounded-md">
            {t("cancel")}
          </Button>
        </div>
      </form>
    </div>
  );
}

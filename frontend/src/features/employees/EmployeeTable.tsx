"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  adminApi,
  employeeApi,
  type ApiError,
  type EmployeeDetail,
  type EmployeeSummary,
} from "@/lib/client-api";
import { cn } from "@/lib/utils";

import { EmployeeForm } from "./EmployeeForm";

type StatusFilter = "active" | "deactivated" | "all";

export function EmployeeTable() {
  const t = useTranslations("employees");
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [status, setStatus] = useState<StatusFilter>("active");
  const [page, setPage] = useState(1);
  const [formMode, setFormMode] = useState<
    { kind: "create" } | { kind: "edit"; employee: EmployeeDetail } | null
  >(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [passwordTarget, setPasswordTarget] = useState<EmployeeSummary | null>(null);

  const listQuery = useQuery({
    queryKey: ["employees", { search: debouncedSearch, status, page }],
    queryFn: ({ signal }) =>
      employeeApi.list({ search: debouncedSearch || undefined, status, page, pageSize: 20 }, signal),
  });

  const onSearchChange = (value: string) => {
    setSearch(value);
    const timer = setTimeout(() => {
      setDebouncedSearch(value);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  };

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["employees"] });
  };

  const deactivate = useMutation({
    mutationFn: (employee: EmployeeSummary) =>
      employeeApi.deactivate(employee.id, undefined),
    onSuccess: () => {
      setActionError(null);
      invalidate();
    },
    onError: (error: ApiError) => setActionError(error.message),
  });

  const reactivate = useMutation({
    mutationFn: (employee: EmployeeSummary) => employeeApi.reactivate(employee.id),
    onSuccess: () => {
      setActionError(null);
      invalidate();
    },
    onError: (error: ApiError) => setActionError(error.message),
  });

  const items = listQuery.data?.ok ? listQuery.data.data.items : [];
  const total = listQuery.data?.ok ? listQuery.data.data.total : 0;
  const totalPages = Math.max(1, Math.ceil(total / 20));

  return (
    <div className="grid gap-6">
      {formMode && (
        <EmployeeForm
          mode={formMode}
          onCancel={() => setFormMode(null)}
          onSaved={() => {
            setFormMode(null);
            invalidate();
          }}
        />
      )}

      <div className="flex flex-wrap items-center gap-3">
        <Input
          type="search"
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder={t("searchPlaceholder")}
          className="h-11 w-full max-w-xs rounded-md"
          aria-label={t("searchPlaceholder")}
        />
        <div role="group" aria-label={t("statusFilter")} className="flex gap-1">
          {(["active", "deactivated", "all"] as StatusFilter[]).map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => {
                setStatus(value);
                setPage(1);
              }}
              aria-pressed={status === value}
              className={cn(
                "flex h-11 items-center rounded-md px-4 text-sm outline-none transition-colors duration-200 focus-visible:ring-2 focus-visible:ring-ring/50",
                status === value
                  ? "bg-brand-soft font-bold text-brand-deep dark:text-brand-bright"
                  : "text-charcoal hover:bg-cloud",
              )}
            >
              {t(`status.${value}`)}
            </button>
          ))}
        </div>
        <Button
          type="button"
          onClick={() => setFormMode({ kind: "create" })}
          className="ms-auto h-11 rounded-md px-6 text-sm font-bold uppercase tracking-wide"
        >
          {t("newEmployee")}
        </Button>
      </div>

      {actionError && (
        <p role="alert" className="text-sm font-bold text-bloom-deep">
          {actionError}
        </p>
      )}

      <div className="overflow-x-auto rounded-xl border border-fog bg-canvas shadow-soft-lift">
        {listQuery.isPending ? (
          <div className="grid gap-3 p-6">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-2/3" />
          </div>
        ) : listQuery.isError ? (
          <p className="p-6 text-sm font-bold text-bloom-deep">{t("errors.generic")}</p>
        ) : items.length === 0 ? (
          <p className="p-6 text-sm text-charcoal">{t("empty")}</p>
        ) : (
          <table className="w-full min-w-[640px] text-sm">
            <thead>
              <tr className="border-b border-fog text-start text-xs uppercase tracking-wide text-graphite">
                <th className="p-4 text-start font-bold">{t("table.name")}</th>
                <th className="p-4 text-start font-bold">{t("table.nationalId")}</th>
                <th className="p-4 text-start font-bold">{t("table.personnelCode")}</th>
                <th className="p-4 text-start font-bold">{t("table.workplace")}</th>
                <th className="p-4 text-start font-bold">{t("table.status")}</th>
                <th className="p-4 text-start font-bold">{t("table.actions")}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((employee) => (
                <tr key={employee.id} className="border-b border-fog last:border-b-0">
                  <td className="p-4 font-bold">
                    {employee.first_name} {employee.last_name}
                  </td>
                  <td className="p-4" dir="ltr">
                    {employee.national_id}
                  </td>
                  <td className="p-4" dir="ltr">
                    {employee.personnel_code}
                  </td>
                  <td className="p-4">{employee.workplace_name}</td>
                  <td className="p-4">
                    <span
                      className={cn(
                        "rounded-lg px-2 py-1 text-xs font-bold",
                        employee.is_active
                          ? "bg-brand-soft text-brand-deep dark:text-brand-bright"
                          : "bg-cloud text-graphite",
                      )}
                    >
                      {employee.is_active ? t("status.active") : t("status.deactivated")}
                    </span>
                  </td>
                  <td className="p-4">
                    <div className="flex flex-wrap gap-2">
                      <RowButton
                        label={t("actions.edit")}
                        onClick={async () => {
                          const detail = await employeeApi.get(employee.id);
                          if (detail.ok) {
                            setFormMode({ kind: "edit", employee: detail.data });
                          } else {
                            setActionError(detail.error.message);
                          }
                        }}
                      />
                      {employee.is_active ? (
                        <RowButton
                          label={t("actions.deactivate")}
                          destructive
                          confirmLabel={t("actions.confirmDeactivate")}
                          onClick={() => deactivate.mutate(employee)}
                        />
                      ) : (
                        <RowButton
                          label={t("actions.reactivate")}
                          onClick={() => reactivate.mutate(employee)}
                        />
                      )}
                      <RowButton
                        label={t("actions.setPassword")}
                        onClick={() => setPasswordTarget(employee)}
                      />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {totalPages > 1 && (
        <nav aria-label={t("pagination")} className="flex items-center gap-3">
          <Button
            type="button"
            variant="outline"
            disabled={page <= 1}
            onClick={() => setPage((current) => current - 1)}
            className="h-11 rounded-md px-4"
          >
            {t("prevPage")}
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
            {t("nextPage")}
          </Button>
        </nav>
      )}

      {passwordTarget && (
        <PasswordDialog
          employee={passwordTarget}
          onClose={() => setPasswordTarget(null)}
          onSaved={() => {
            setPasswordTarget(null);
            setActionError(null);
          }}
        />
      )}
    </div>
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

function PasswordDialog({
  employee,
  onClose,
  onSaved,
}: {
  employee: EmployeeSummary;
  onClose: () => void;
  onSaved: () => void;
}) {
  const t = useTranslations("employees");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const detailQuery = useQuery({
    queryKey: ["employees", "detail", employee.id],
    queryFn: () => employeeApi.get(employee.id),
  });

  const submit = async () => {
    setBusy(true);
    setError(null);
    const detail = detailQuery.data?.ok ? detailQuery.data.data : null;
    if (!detail) {
      setError(t("errors.generic"));
      setBusy(false);
      return;
    }
    const result = await adminApi.setPassword(detail.user.id, password);
    setBusy(false);
    if (result.ok) {
      onSaved();
    } else {
      setError(result.error.message);
    }
  };

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center p-4">
      <div
        role="presentation"
        onClick={onClose}
        className="absolute inset-0 bg-black/40 motion-safe:animate-in motion-safe:fade-in-0 motion-safe:duration-200"
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={t("actions.setPassword")}
        className="relative w-full max-w-md rounded-xl border border-fog bg-canvas p-6 shadow-floating-modal"
      >
        <h3 className="mb-4 text-lg font-bold">{t("passwordDialog.title")}</h3>
        <p className="mb-4 text-sm text-charcoal">
          {t("passwordDialog.description", {
            name: `${employee.first_name} ${employee.last_name}`,
          })}
        </p>
        <Input
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          className="mb-4 h-11 rounded-md"
          autoComplete="new-password"
          aria-label={t("form.password")}
        />
        {error && (
          <p role="alert" className="mb-4 text-sm font-bold text-bloom-deep">
            {error}
          </p>
        )}
        <div className="flex gap-3">
          <Button type="button" onClick={submit} disabled={busy || password.length < 8} className="h-11 rounded-md px-6">
            {busy ? t("form.saving") : t("passwordDialog.submit")}
          </Button>
          <Button type="button" variant="outline" onClick={onClose} className="h-11 rounded-md px-6">
            {t("form.cancel")}
          </Button>
        </div>
      </div>
    </div>
  );
}

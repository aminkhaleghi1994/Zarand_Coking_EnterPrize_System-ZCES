"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import { useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  loanApi,
  orgApi,
  warehouseApi,
  type ApiError,
  type LoanPolicy,
  type LoanRequest,
} from "@/lib/client-api";
import { LoanPolicyInputSchema, LoanRequestInputSchema } from "@/lib/schemas";
import { cn } from "@/lib/utils";
import { formatWarehouseTimestamp, warehouseErrorMessage } from "@/features/warehouse/shared";

const PAGE_SIZE = 20;

type Tab = "policies" | "requests";
type StatusFilter = "all" | "pending" | "active" | "settled" | "cancelled";
type TypeFilter = "all" | "loan" | "guarantee";

export function LoansConsole() {
  const t = useTranslations("loans");
  const [tab, setTab] = useState<Tab>("requests");
  const [actionError, setActionError] = useState<string | null>(null);

  return (
    <div className="grid gap-6">
      <div role="tablist" aria-label={t("filterLabel")} className="flex flex-wrap gap-1">
        {(["requests", "policies"] as Tab[]).map((value) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={tab === value}
            onClick={() => setTab(value)}
            className={cn(
              "flex h-11 items-center rounded-md px-5 text-sm outline-none transition-colors duration-200 focus-visible:ring-2 focus-visible:ring-ring/50",
              tab === value
                ? "bg-brand-soft font-bold text-brand-deep dark:text-brand-bright"
                : "text-charcoal hover:bg-cloud",
            )}
          >
            {value === "policies" ? t("tabPolicies") : t("tabRequests")}
          </button>
        ))}
      </div>

      {actionError ? (
        <p role="alert" className="text-sm font-bold text-bloom-deep">
          {actionError}
        </p>
      ) : null}

      {tab === "policies" ? <PoliciesView onError={setActionError} /> : <RequestsView onError={setActionError} />}
    </div>
  );
}

function PoliciesView({ onError }: { onError: (message: string) => void }) {
  const t = useTranslations("loans");
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<LoanPolicy | null>(null);
  const [creating, setCreating] = useState(false);
  const [yearFilter, setYearFilter] = useState("");

  const identity = useQuery({
    queryKey: ["me"],
    queryFn: ({ signal }) => warehouseApi.me(signal),
  });
  const canManage = Boolean(
    identity.data?.ok && identity.data.data.permissions.includes("loan:policy:create"),
  );

  const year = yearFilter ? Number(yearFilter) : undefined;
  const listQuery = useQuery({
    queryKey: ["loan-policies", year],
    queryFn: ({ signal }) =>
      loanApi.policies.list({ year: Number.isFinite(year as number) ? year : undefined, pageSize: PAGE_SIZE }, signal),
  });
  const policies = listQuery.data?.ok ? listQuery.data.data.items : [];

  const retire = useMutation({
    mutationFn: (policy: LoanPolicy) => loanApi.policies.retire(policy.id, policy.version),
    onSuccess: () => {
      onError("");
      void queryClient.invalidateQueries({ queryKey: ["loan-policies"] });
    },
    onError: (error: ApiError) => onError(warehouseErrorMessage(t, error)),
  });

  const refresh = () => {
    onError("");
    void queryClient.invalidateQueries({ queryKey: ["loan-policies"] });
  };

  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-center gap-3">
        <Input
          type="number"
          inputMode="numeric"
          value={yearFilter}
          onChange={(event) => setYearFilter(event.target.value)}
          placeholder={t("yearLabel")}
          aria-label={t("yearLabel")}
          className="h-11 w-32 rounded-md"
        />
        {canManage ? (
          <Button
            type="button"
            onClick={() => setCreating((current) => !current)}
            className="ms-auto h-11 rounded-md"
          >
            {t("composePolicy")}
          </Button>
        ) : null}
      </div>

      {creating && canManage ? (
        <PolicyForm
          onCancel={() => setCreating(false)}
          onSaved={() => {
            setCreating(false);
            refresh();
          }}
        />
      ) : null}

      {editing && canManage ? (
        <PolicyForm
          policy={editing}
          onCancel={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            refresh();
          }}
        />
      ) : null}

      {listQuery.isPending ? (
        <div className="grid gap-2">
          <LoanSkeletonRow />
          <LoanSkeletonRow />
        </div>
      ) : policies.length === 0 ? (
        <p className="p-6 text-center text-graphite">{t("empty")}</p>
      ) : (
        <div className="grid gap-3">
          {policies.map((policy) => (
            <PolicyCard
              key={policy.id}
              policy={policy}
              canManage={canManage}
              onEdit={() => setEditing(policy)}
              onRetire={() => retire.mutate(policy)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function PolicyCard({
  policy,
  canManage,
  onEdit,
  onRetire,
}: {
  policy: LoanPolicy;
  canManage: boolean;
  onEdit: () => void;
  onRetire: () => void;
}) {
  const t = useTranslations("loans");
  return (
    <div className="grid gap-2 rounded-xl border border-fog bg-canvas p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-bold">
          {policy.workplace.name} · {policy.year}
        </p>
        <span
          className={cn(
            "rounded-lg px-2 py-0.5 text-xs font-bold",
            policy.is_active
              ? "bg-brand-soft text-brand-deep dark:text-brand-bright"
              : "bg-cloud text-graphite",
          )}
        >
          {policy.is_active ? t("policy.active") : t("policy.paused")}
        </span>
      </div>
      <ul className="grid gap-1 text-sm md:grid-cols-2">
        <li>
          {t("policy.maxLoanAmount")}: <span className="font-bold" dir="ltr">{policy.max_loan_amount}</span>
        </li>
        <li>
          {t("policy.maxGuaranteeAmount")}: <span className="font-bold" dir="ltr">{policy.max_guarantee_amount}</span>
        </li>
        <li>
          {t("policy.countPerYear")}: <span className="font-bold">{policy.max_request_count_per_year}</span>
        </li>
        <li>
          {t("policy.countLifetime")}: <span className="font-bold">{policy.max_request_count_lifetime}</span>
        </li>
      </ul>
      {canManage ? (
        <div className="flex gap-2">
          <RowButton label={t("actions.edit")} onClick={onEdit} />
          <RowButton label={t("actions.retire")} destructive confirmLabel={t("actions.retire")} onClick={onRetire} />
        </div>
      ) : null}
    </div>
  );
}

function PolicyForm({
  policy,
  onCancel,
  onSaved,
}: {
  policy?: LoanPolicy;
  onCancel: () => void;
  onSaved: () => void;
}) {
  const t = useTranslations("loans.policyForm");
  const tRoot = useTranslations("loans");
  const editing = Boolean(policy);
  const [workplaceId, setWorkplaceId] = useState(policy?.workplace.id ?? "");
  const [year, setYear] = useState(String(policy?.year ?? ""));
  const [maxLoan, setMaxLoan] = useState(policy?.max_loan_amount ?? "");
  const [maxGuarantee, setMaxGuarantee] = useState(policy?.max_guarantee_amount ?? "");
  const [perYear, setPerYear] = useState(String(policy?.max_request_count_per_year ?? ""));
  const [lifetime, setLifetime] = useState(String(policy?.max_request_count_lifetime ?? ""));
  const [error, setError] = useState<string | null>(null);

  const workplacesQuery = useQuery({
    queryKey: ["org-workplaces"],
    queryFn: ({ signal }) => orgApi.workplaces(signal),
  });
  const workplaces = workplacesQuery.data?.ok ? workplacesQuery.data.data.items : [];

  const save = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      editing
        ? loanApi.policies.update(policy!.id, { ...payload, version: policy!.version })
        : loanApi.policies.create(payload),
    onSuccess: () => {
      setError(null);
      onSaved();
    },
    onError: (mutationError: ApiError) => setError(ruleAwareMessage(tRoot, mutationError)),
  });

  const submit = () => {
    setError(null);
    const parsed = LoanPolicyInputSchema.safeParse({
      workplace_id: workplaceId,
      year,
      max_loan_amount: maxLoan,
      max_guarantee_amount: maxGuarantee,
      max_request_count_per_year: perYear,
      max_request_count_lifetime: lifetime,
    });
    if (!parsed.success) {
      const key = parsed.error.issues[0]?.message ?? "loans.errors.generic";
      setError(tRoot.has(key) ? tRoot(key) : tRoot("errors.generic"));
      return;
    }
    const payload: Record<string, unknown> = editing
      ? {
          year: parsed.data.year,
          max_loan_amount: parsed.data.max_loan_amount,
          max_guarantee_amount: parsed.data.max_guarantee_amount,
          max_request_count_per_year: parsed.data.max_request_count_per_year,
          max_request_count_lifetime: parsed.data.max_request_count_lifetime,
          version: policy!.version,
        }
      : parsed.data;
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
      <div className="grid gap-2">
        <Label htmlFor="policy-workplace">{tRoot("policy.workplace")}</Label>
        <select
          id="policy-workplace"
          required
          disabled={editing}
          value={workplaceId}
          onChange={(event) => setWorkplaceId(event.target.value)}
          className="h-11 rounded-md border border-steel bg-canvas px-3 text-sm disabled:bg-cloud disabled:text-graphite"
        >
          <option value="">{tRoot("policy.workplacePlaceholder")}</option>
          {workplaces.map((workplace) => (
            <option key={workplace.id} value={workplace.id}>
              {workplace.name} · {workplace.code}
            </option>
          ))}
        </select>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <Field label={tRoot("policy.year")} value={year} onChange={setYear} dir="ltr" />
        <Field label={tRoot("policy.maxLoanAmount")} value={maxLoan} onChange={setMaxLoan} dir="ltr" />
        <Field label={tRoot("policy.maxGuaranteeAmount")} value={maxGuarantee} onChange={setMaxGuarantee} dir="ltr" />
        <Field label={tRoot("policy.countPerYear")} value={perYear} onChange={setPerYear} dir="ltr" />
        <Field label={tRoot("policy.countLifetime")} value={lifetime} onChange={setLifetime} dir="ltr" />
      </div>
      <div className="flex gap-2">
        <Button type="submit" disabled={save.isPending} className="h-11 rounded-md">
          {save.isPending ? t("saving") : editing ? t("save") : t("submit")}
        </Button>
        <Button type="button" variant="outline" onClick={onCancel} className="h-11 rounded-md">
          {t("cancel")}
        </Button>
      </div>
    </form>
  );
}

function Field({
  label,
  value,
  onChange,
  dir,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  dir?: "ltr" | "rtl";
}) {
  return (
    <div className="grid gap-2">
      <Label>{label}</Label>
      <Input
        required
        dir={dir}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-11 rounded-md"
      />
    </div>
  );
}

function RequestsView({ onError }: { onError: (message: string) => void }) {
  const t = useTranslations("loans");
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<StatusFilter>("all");
  const [type, setType] = useState<TypeFilter>("all");
  const [submitting, setSubmitting] = useState(false);

  const identity = useQuery({
    queryKey: ["me"],
    queryFn: ({ signal }) => warehouseApi.me(signal),
  });
  const permissions: string[] = identity.data?.ok ? identity.data.data.permissions : [];
  const canActivate = permissions.includes("loan:request:activate");
  const canSettle = permissions.includes("loan:request:settle");
  const canCancel = permissions.includes("loan:request:cancel");

  const listQuery = useQuery({
    queryKey: ["loan-requests", status, type],
    queryFn: ({ signal }) =>
      loanApi.requests.list(
        { status, type: type === "all" ? undefined : type, pageSize: PAGE_SIZE },
        signal,
      ),
  });
  const requests = listQuery.data?.ok ? listQuery.data.data.items : [];

  const transition = useMutation({
    mutationFn: ({ request, action }: { request: LoanRequest; action: "activate" | "settle" | "cancel" }) =>
      action === "activate"
        ? loanApi.requests.activate(request.id, request.version)
        : action === "settle"
          ? loanApi.requests.settle(request.id, request.version)
          : loanApi.requests.cancel(request.id, request.version),
    onSuccess: () => {
      onError("");
      void queryClient.invalidateQueries({ queryKey: ["loan-requests"] });
    },
    onError: (error: ApiError) => onError(ruleAwareMessage(t, error)),
  });

  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-center gap-3">
        <div role="group" aria-label={t("typeLabel")} className="flex flex-wrap gap-1">
          {(["all", "loan", "guarantee"] as TypeFilter[]).map((value) => (
            <Chip key={value} active={type === value} onClick={() => setType(value)}>
              {value === "all" ? t("status.all") : value === "loan" ? t("request.typeLoan") : t("request.typeGuarantee")}
            </Chip>
          ))}
        </div>
        <div role="group" aria-label={t("statusLabel")} className="flex flex-wrap gap-1">
          {(["all", "pending", "active", "settled", "cancelled"] as StatusFilter[]).map((value) => (
            <Chip key={value} active={status === value} onClick={() => setStatus(value)}>
              {value === "all" ? t("status.all") : t(`status.${value}`)}
            </Chip>
          ))}
        </div>
        <Button
          type="button"
          onClick={() => setSubmitting((current) => !current)}
          className="ms-auto h-11 rounded-md"
        >
          {t("composeRequest")}
        </Button>
      </div>

      {submitting ? (
        <LoanForm
          onCancel={() => setSubmitting(false)}
          onSubmitted={() => {
            setSubmitting(false);
            onError("");
            void queryClient.invalidateQueries({ queryKey: ["loan-requests"] });
          }}
        />
      ) : null}

      {listQuery.isPending ? (
        <div className="grid gap-2">
          <LoanSkeletonRow />
          <LoanSkeletonRow />
        </div>
      ) : requests.length === 0 ? (
        <p className="p-6 text-center text-graphite">{t("empty")}</p>
      ) : (
        <div className="grid gap-3">
          {requests.map((request) => (
            <RequestCard
              key={request.id}
              request={request}
              canActivate={canActivate}
              canSettle={canSettle}
              canCancel={canCancel}
              onTransition={(action) => transition.mutate({ request, action })}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function RequestCard({
  request,
  canActivate,
  canSettle,
  canCancel,
  onTransition,
}: {
  request: LoanRequest;
  canActivate: boolean;
  canSettle: boolean;
  canCancel: boolean;
  onTransition: (action: "activate" | "settle" | "cancel") => void;
}) {
  const t = useTranslations("loans");
  const locale = useLocale();
  return (
    <div className="grid gap-2 rounded-xl border border-fog bg-canvas p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-bold">
          {request.employee.name}
          <span className="text-graphite"> · {request.workplace.name}</span>
        </p>
        <span
          className={cn(
            "rounded-lg px-2 py-0.5 text-xs font-bold",
            request.status === "active"
              ? "bg-brand-soft text-brand-deep dark:text-brand-bright"
              : request.status === "settled"
                ? "bg-cloud text-ink"
                : request.status === "cancelled"
                  ? "bg-bloom-wine/10 text-bloom-deep"
                  : "bg-cloud text-charcoal",
          )}
        >
          {t(`status.${request.status}`)}
        </span>
      </div>
      <p className="text-sm">
        {request.type === "loan" ? t("request.typeLoan") : t("request.typeGuarantee")} ·{" "}
        <span className="font-bold" dir="ltr">
          {request.amount}
        </span>{" "}
        · {t("request.year")}: {request.year}
      </p>
      <p className="text-xs text-graphite">
        {formatWarehouseTimestamp(request.created_at, locale)}
        {request.settled_at
          ? ` · ${t("request.settledAt")}: ${formatWarehouseTimestamp(request.settled_at, locale)}`
          : null}
      </p>
      {(request.status === "pending" && canActivate) ||
      (request.status === "active" && (canSettle || canCancel)) ? (
        <div className="flex flex-wrap gap-2">
          {request.status === "pending" && canActivate ? (
            <RowButton label={t("actions.activate")} onClick={() => onTransition("activate")} />
          ) : null}
          {request.status === "active" && canSettle ? (
            <RowButton
              label={t("actions.settle")}
              destructive
              confirmLabel={t("actions.settle")}
              onClick={() => onTransition("settle")}
            />
          ) : null}
          {request.status === "active" && canCancel ? (
            <RowButton
              label={t("actions.cancel")}
              destructive
              confirmLabel={t("actions.cancel")}
              onClick={() => onTransition("cancel")}
            />
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function LoanForm({ onCancel, onSubmitted }: { onCancel: () => void; onSubmitted: () => void }) {
  const t = useTranslations("loans.loanForm");
  const tRoot = useTranslations("loans");
  const [type, setType] = useState<"loan" | "guarantee">("loan");
  const [amount, setAmount] = useState("");
  const [error, setError] = useState<string | null>(null);

  const submitMutation = useMutation({
    mutationFn: (payload: unknown) => loanApi.requests.submit(payload),
    onSuccess: () => {
      setError(null);
      onSubmitted();
    },
    onError: (mutationError: ApiError) => setError(ruleAwareMessage(tRoot, mutationError)),
  });

  const submit = () => {
    setError(null);
    const parsed = LoanRequestInputSchema.safeParse({ type, amount });
    if (!parsed.success) {
      const key = parsed.error.issues[0]?.message ?? "loans.errors.generic";
      setError(tRoot.has(key) ? tRoot(key) : tRoot("errors.generic"));
      return;
    }
    submitMutation.mutate(parsed.data);
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
      <fieldset className="grid gap-2">
        <legend className="mb-1 text-xs font-bold uppercase tracking-widest text-graphite">
          {tRoot("request.type")}
        </legend>
        <div className="flex gap-2">
          {(["loan", "guarantee"] as const).map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => setType(value)}
              aria-pressed={type === value}
              className={cn(
                "flex h-11 flex-1 items-center justify-center rounded-md border px-4 text-sm outline-none transition-colors duration-200 focus-visible:ring-2 focus-visible:ring-ring/50",
                type === value
                  ? "border-brand bg-brand-soft font-bold text-brand-deep dark:text-brand-bright"
                  : "border-fog text-charcoal hover:bg-cloud",
              )}
            >
              {value === "loan" ? t("typeLoan") : t("typeGuarantee")}
            </button>
          ))}
        </div>
      </fieldset>
      <div className="grid gap-2">
        <Label htmlFor="loan-amount">{t("amount")}</Label>
        <Input
          id="loan-amount"
          required
          dir="ltr"
          inputMode="decimal"
          value={amount}
          onChange={(event) => setAmount(event.target.value)}
          aria-describedby="loan-amount-hint"
          className="h-11 rounded-md"
        />
        <p id="loan-amount-hint" className="text-xs text-graphite">
          {t("amountHint")}
        </p>
      </div>
      <div className="flex gap-2">
        <Button type="submit" disabled={submitMutation.isPending} className="h-11 rounded-md">
          {submitMutation.isPending ? t("submitting") : t("submit")}
        </Button>
        <Button type="button" variant="outline" onClick={onCancel} className="h-11 rounded-md">
          {t("cancel")}
        </Button>
      </div>
    </form>
  );
}

function ruleAwareMessage(
  t: {
    (key: string, values?: Record<string, string | number | Date>): string;
    has?(key: string): boolean;
  },
  error: ApiError,
): string {
  const envelope = error as ApiError & { details?: Record<string, string | number | Date> };
  const rule = envelope.details?.rule;
  if (typeof rule === "string") {
    const key = `rules.${rule}`;
    if (t.has?.(key)) {
      return t(key, envelope.details);
    }
  }
  return warehouseErrorMessage(t, error);
}

function Chip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "flex h-11 items-center rounded-md px-4 text-sm outline-none transition-colors duration-200 focus-visible:ring-2 focus-visible:ring-ring/50",
        active
          ? "bg-brand-soft font-bold text-brand-deep dark:text-brand-bright"
          : "text-charcoal hover:bg-cloud",
      )}
    >
      {children}
    </button>
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

function LoanSkeletonRow() {
  return <Skeleton className="h-16 w-full" />;
}

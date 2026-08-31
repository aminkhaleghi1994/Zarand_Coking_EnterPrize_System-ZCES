"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  requestApi,
  warehouseApi,
  type ApiError,
  type Placement,
  type RequestRecord,
} from "@/lib/client-api";
import { formatWarehouseTimestamp } from "@/features/warehouse/shared";
import { warehouseErrorMessage } from "@/features/warehouse/shared";
import { RequestForm } from "./RequestForm";

type StatusFilter = "all" | "pending" | "approved" | "rejected" | "fulfilled";

export function RequestsView() {
  const t = useTranslations("requests");
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<StatusFilter>("all");
  const [composing, setComposing] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const identity = useQuery({
    queryKey: ["me"],
    queryFn: ({ signal }) => warehouseApi.me(signal),
  });
  const listQuery = useQuery({
    queryKey: ["warehouse-requests", filter],
    queryFn: ({ signal }) => requestApi.list(filter, signal),
  });

  const permissions = identity.data?.ok ? identity.data.data.permissions : [];
  const canDecide = permissions.includes("warehouse:request:decide");
  const canFulfill = permissions.includes("warehouse:request:fulfill");

  const requests = listQuery.data?.ok ? listQuery.data.data.items : [];

  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div role="group" aria-label={t("filterLabel")} className="flex flex-wrap gap-1">
          {(["all", "pending", "approved", "rejected", "fulfilled"] as StatusFilter[]).map(
            (value) => (
              <button
                key={value}
                type="button"
                onClick={() => setFilter(value)}
                aria-pressed={filter === value}
                className={
                  "flex h-11 items-center rounded-md px-4 text-sm outline-none transition-colors duration-200 focus-visible:ring-2 focus-visible:ring-ring/50 " +
                  (filter === value
                    ? "bg-brand-soft font-bold text-brand-deep dark:text-brand-bright"
                    : "text-charcoal hover:bg-cloud")
                }
              >
                {t(`status.${value}`)}
              </button>
            ),
          )}
        </div>
        <Button
          type="button"
          onClick={() => setComposing((current) => !current)}
          className="h-11 rounded-md"
        >
          {t("compose")}
        </Button>
      </div>

      {actionError ? (
        <p role="alert" className="text-sm font-bold text-bloom-deep">
          {actionError}
        </p>
      ) : null}

      {composing ? (
        <RequestForm
          onCreated={() => {
            setComposing(false);
            void queryClient.invalidateQueries({ queryKey: ["warehouse-requests"] });
          }}
        />
      ) : null}

      {listQuery.isPending ? (
        <div className="grid gap-2">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      ) : (
        <div className="grid gap-3">
          {requests.map((request) => (
            <RequestCard
              key={request.id}
              request={request}
              canDecide={canDecide}
              canFulfill={canFulfill}
              onError={setActionError}
            />
          ))}
          {requests.length === 0 ? (
            <p className="p-6 text-center text-graphite">{t("empty")}</p>
          ) : null}
        </div>
      )}
    </div>
  );
}

type RequestCardProps = {
  request: RequestRecord;
  canDecide: boolean;
  canFulfill: boolean;
  onError: (message: string) => void;
};

function RequestCard({ request, canDecide, canFulfill, onError }: RequestCardProps) {
  const t = useTranslations("requests");
  const locale = useLocale();
  const [fulfilling, setFulfilling] = useState(false);

  return (
    <div className="grid gap-3 rounded-xl border border-fog bg-canvas p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-bold">{request.purpose_description}</p>
        <span
          className={
            "rounded-lg px-2 py-0.5 text-xs font-bold " +
            (request.status === "fulfilled"
              ? "bg-brand-soft text-brand-deep dark:text-brand-bright"
              : request.status === "rejected"
                ? "bg-bloom-wine/10 text-bloom-deep"
                : request.status === "approved"
                  ? "bg-cloud text-ink"
                  : "bg-cloud text-charcoal")
          }
        >
          {t(`status.${request.status}`)}
        </span>
      </div>
      <p className="text-xs text-graphite">
        {request.requested_by_email ?? request.requested_by} ·{" "}
        {formatWarehouseTimestamp(request.created_at, locale)}
      </p>
      <ul className="grid gap-1 text-sm">
        {request.lines.map((line) => (
          <li key={line.id} className="flex flex-wrap items-center justify-between gap-2">
            <span>
              {line.item.name}
              <span className="text-graphite"> · {line.item.code ?? "—"}</span>
              {line.note ? <span className="text-graphite"> · {line.note}</span> : null}
            </span>
            <span className="font-bold">
              {line.quantity} <span className="text-xs text-graphite">{line.item.unit}</span>
            </span>
          </li>
        ))}
      </ul>
      {request.decision_note ? (
        <p className="text-sm text-charcoal">{t("decisionNote", { note: request.decision_note })}</p>
      ) : null}

      {request.status === "pending" && canDecide ? (
        <DecisionButtons request={request} onError={onError} />
      ) : null}
      {request.status === "approved" && canFulfill ? (
        <div>
          <Button type="button" onClick={() => setFulfilling(true)} className="h-11 rounded-md">
            {t("fulfill")}
          </Button>
        </div>
      ) : null}
      {fulfilling ? (
        <FulfillDialog request={request} onClose={() => setFulfilling(false)} onError={onError} />
      ) : null}
    </div>
  );
}

function DecisionButtons({
  request,
  onError,
}: {
  request: RequestRecord;
  onError: (message: string) => void;
}) {
  const t = useTranslations("requests");
  const queryClient = useQueryClient();
  const [note, setNote] = useState("");

  const decide = useMutation({
    mutationFn: (decision: "approve" | "reject") =>
      decision === "approve"
        ? requestApi.approve(request.id, request.version, note)
        : requestApi.reject(request.id, request.version, note),
    onSuccess: () => {
      onError("");
      void queryClient.invalidateQueries({ queryKey: ["warehouse-requests"] });
    },
    onError: (error: ApiError) => onError(warehouseErrorMessage(t, error)),
  });

  return (
    <div className="grid gap-2">
      <Input
        value={note}
        onChange={(event) => setNote(event.target.value)}
        placeholder={t("decisionNotePlaceholder")}
        aria-label={t("decisionNotePlaceholder")}
        className="h-11 rounded-md"
      />
      <div className="flex gap-2">
        <Button
          type="button"
          onClick={() => decide.mutate("approve")}
          disabled={decide.isPending}
          className="h-11 rounded-md"
        >
          {t("approve")}
        </Button>
        <Button
          type="button"
          variant="outline"
          onClick={() => decide.mutate("reject")}
          disabled={decide.isPending}
          className="h-11 rounded-md"
        >
          {t("reject")}
        </Button>
      </div>
    </div>
  );
}

function FulfillDialog({
  request,
  onClose,
  onError,
}: {
  request: RequestRecord;
  onClose: () => void;
  onError: (message: string) => void;
}) {
  const t = useTranslations("requests.fulfill");
  const [picks, setPicks] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  const submit = useMutation({
    mutationFn: () =>
      requestApi.fulfill(
        request.id,
        request.version,
        request.lines.map((line) => ({ line_id: line.id, placement_id: picks[line.id] })),
      ),
    onSuccess: () => {
      onError("");
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
      <h3 className="text-lg font-bold">{t("title")}</h3>
      {error ? (
        <p role="alert" className="text-sm font-bold text-bloom-deep">
          {error}
        </p>
      ) : null}
      {request.lines.map((line) => (
        <PlacementPicker
          key={line.id}
          line={line}
          value={picks[line.id] ?? ""}
          onChange={(placementId) => setPicks((current) => ({ ...current, [line.id]: placementId }))}
        />
      ))}
      <div className="flex gap-2">
        <Button type="submit" disabled={submit.isPending} className="h-11 rounded-md">
          {submit.isPending ? t("submitting") : t("submit")}
        </Button>
        <Button type="button" variant="outline" onClick={onClose} className="h-11 rounded-md">
          {t("cancel")}
        </Button>
      </div>
    </form>
  );
}

function PlacementPicker({
  line,
  value,
  onChange,
}: {
  line: RequestRecord["lines"][number];
  value: string;
  onChange: (placementId: string) => void;
}) {
  const t = useTranslations("requests.fulfill");
  const placements = useQuery({
    queryKey: ["warehouse-placements-for-line", line.item.id],
    queryFn: ({ signal }) =>
      warehouseApi.placements.list({ itemId: line.item.id, pageSize: 100 }, signal),
  });

  const options: Placement[] = placements.data?.ok ? placements.data.data.items : [];

  return (
    <div className="grid gap-2 rounded-lg border border-fog p-3">
      <Label>
        {line.item.name} — {line.quantity} {line.item.unit}
      </Label>
      <select
        required
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-11 rounded-md border border-steel bg-canvas px-3 text-sm"
      >
        <option value="">{t("placementPlaceholder")}</option>
        {options.map((placement) => (
          <option key={placement.id} value={placement.id}>
            {placement.warehouse.name} · {placement.shelf.code} · {placement.quantity}{" "}
            {placement.item.unit}
          </option>
        ))}
      </select>
    </div>
  );
}

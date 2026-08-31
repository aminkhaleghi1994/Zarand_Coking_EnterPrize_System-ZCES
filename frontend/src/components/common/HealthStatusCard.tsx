"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";

import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

type HealthPayload = {
  status: string;
  version: string;
  components: Record<string, { status: "up" | "down"; latency_ms?: number | null }>;
};

async function fetchHealth(): Promise<HealthPayload> {
  const response = await fetch("/api/health", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`health request failed: ${response.status}`);
  }
  return (await response.json()) as HealthPayload;
}

export function HealthStatusCard() {
  const t = useTranslations("home");
  const { isPending, isError, data } = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    refetchInterval: 30_000,
  });

  const backendUp = !isPending && !isError && data.status === "ok";
  const databaseUp = !isPending && !isError && data.components.database?.status === "up";
  const latency = data?.components.database?.latency_ms;

  return (
    <div
      aria-busy={isPending}
      className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3"
    >
      <StatusTile
        label={t("backend")}
        pending={isPending}
        up={backendUp}
        detail={isError ? t("statusDown") : backendUp ? t("statusUp") : undefined}
      />
      <StatusTile
        label={t("database")}
        pending={isPending}
        up={databaseUp}
        detail={
          isError
            ? t("statusDown")
            : databaseUp
              ? latency != null
                ? t("latency", { ms: latency })
                : t("statusUp")
              : undefined
        }
      />
      <StatusTile
        label={t("version")}
        pending={isPending}
        detail={isError ? undefined : data?.version}
      />
    </div>
  );
}

function StatusTile({
  label,
  detail,
  pending,
  up,
}: {
  label: string;
  detail?: string;
  pending: boolean;
  up?: boolean;
}) {
  return (
    <div className="rounded-xl border border-fog bg-canvas p-5 shadow-soft-lift">
      <p className="text-sm text-charcoal">{label}</p>
      {pending ? (
        <Skeleton className="mt-2 h-6 w-28" />
      ) : (
        <p className="mt-1 flex items-center gap-2 text-lg font-bold">
          {up !== undefined && <StatusDot up={up} />}
          <span className={cn(up === false && "text-bloom-deep")}>{detail ?? "—"}</span>
        </p>
      )}
    </div>
  );
}

function StatusDot({ up }: { up: boolean }) {
  return (
    <span
      aria-hidden
      className={cn(
        "inline-block size-2.5 shrink-0 rounded-full",
        up ? "bg-brand" : "bg-bloom-deep",
      )}
    />
  );
}

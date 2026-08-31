"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

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

  return (
    <Card className="w-full max-w-md shadow-soft-lift">
      <CardHeader>
        <CardTitle className="text-xl font-bold">{t("healthTitle")}</CardTitle>
        <CardDescription className="text-graphite">{t("healthDescription")}</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3 text-sm">
        {isPending ? (
          <>
            <Skeleton className="h-6 w-40" />
            <Skeleton className="h-6 w-56" />
            <Skeleton className="h-6 w-48" />
          </>
        ) : isError ? (
          <p className="font-bold text-bloom-deep">{t("statusDown")}</p>
        ) : (
          <>
            <div className="flex items-center justify-between gap-4">
              <span className="text-charcoal">{t("backend")}</span>
              <span className="flex items-center gap-2 font-bold">
                <StatusDot up={data.status === "ok"} />
                {data.status === "ok" ? t("statusUp") : t("statusDown")}
              </span>
            </div>
            <div className="flex items-center justify-between gap-4">
              <span className="text-charcoal">{t("database")}</span>
              <span className="flex items-center gap-2 font-bold">
                <StatusDot up={data.components.database?.status === "up"} />
                {data.components.database?.status === "up" ? t("statusUp") : t("statusDown")}
              </span>
            </div>
            <div className="flex items-center justify-between gap-4">
              <span className="text-charcoal">v</span>
              <span className="font-bold">{data.version}</span>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function StatusDot({ up }: { up: boolean }) {
  return (
    <span
      aria-hidden
      className={`inline-block size-2 rounded-full ${up ? "bg-brand" : "bg-bloom-deep"}`}
    />
  );
}

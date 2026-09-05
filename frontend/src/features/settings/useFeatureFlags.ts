"use client";

import { useQuery } from "@tanstack/react-query";

import { settingsApi, type SettingRecord } from "@/lib/client-api";

export type FeatureFlags = {
  loansEnabled: boolean;
  assetsEnabled: boolean;
  showRequestsBreakdown: boolean;
  showAlertsBreakdown: boolean;
};

export const DEFAULT_FLAGS: FeatureFlags = {
  loansEnabled: true,
  assetsEnabled: true,
  showRequestsBreakdown: true,
  showAlertsBreakdown: true,
};

function flagValue(settings: SettingRecord[] | undefined, key: string): boolean {
  const setting = settings?.find((item) => item.key === key);
  return setting?.value_type === "boolean" ? setting.value === true : true;
}

/**
 * Settings-backed flags (T017/T020). Fail-open: while loading or on error
 * the defaults apply (missing rows fall back to code defaults everywhere —
 * the same rule as the backend contract).
 */
export function useFeatureFlags() {
  const settingsQuery = useQuery({
    queryKey: ["settings", "list"],
    queryFn: ({ signal }) => settingsApi.list(signal),
    staleTime: 60 * 1000,
  });

  const settings = settingsQuery.data?.ok ? settingsQuery.data.data.items : undefined;
  const flags: FeatureFlags = {
    loansEnabled: flagValue(settings, "flags.loan_module_enabled"),
    assetsEnabled: flagValue(settings, "flags.asset_module_enabled"),
    showRequestsBreakdown: flagValue(settings, "dashboard.show_requests_breakdown"),
    showAlertsBreakdown: flagValue(settings, "dashboard.show_alerts_breakdown"),
  };
  return { flags, settingsQuery, settings };
}

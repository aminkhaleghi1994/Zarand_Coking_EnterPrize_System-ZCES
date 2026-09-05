"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { settingsApi, type ApiError, type SettingRecord } from "@/lib/client-api";

type DraftState = { value: string; version: number };

function settingKeyLocale(setting: SettingRecord, locale: string): string {
  return locale === "fa" ? setting.description_fa : setting.description;
}

function parseDraft(setting: SettingRecord, raw: string): unknown {
  if (setting.value_type === "boolean") {
    return raw === "true";
  }
  if (setting.value_type === "integer") {
    return Number.parseInt(raw, 10);
  }
  if (setting.value_type === "json") {
    return JSON.parse(raw) as unknown;
  }
  return raw;
}

function initialDraft(setting: SettingRecord): string {
  if (setting.value_type === "json") {
    return JSON.stringify(setting.value);
  }
  return String(setting.value);
}

/**
 * Settings console (T017, US4): grouped typed controls over the global
 * setting rows — boolean switches, integer inputs, JSON textareas — with
 * optimistic-version guarding (stale writes rejected and surfaced, then
 * the form refetches so the operator retries against the fresh version).
 */
export function SettingsConsole() {
  const t = useTranslations("settings");
  const locale = useLocale();
  const queryClient = useQueryClient();
  const [drafts, setDrafts] = useState<Record<string, DraftState>>({});
  const [feedback, setFeedback] = useState<{ key: string; message: string } | null>(
    null,
  );

  const settingsQuery = useQuery({
    queryKey: ["settings", "list"],
    queryFn: ({ signal }) => settingsApi.list(signal),
  });

  const save = useMutation({
    mutationFn: ({
      setting,
      raw,
      version,
    }: {
      setting: SettingRecord;
      raw: string;
      version: number;
    }) => settingsApi.update(setting.key, parseDraft(setting, raw), version),
    onSuccess: (_data, variables) => {
      setFeedback({ key: variables.setting.key, message: t("saved") });
      void queryClient.invalidateQueries({ queryKey: ["settings"] });
      setDrafts((current) => {
        const next = { ...current };
        delete next[variables.setting.key];
        return next;
      });
    },
    onError: (error: ApiError, variables) => {
      const message =
        error.code === "STALE_VERSION" || error.code === "CONFLICT_CONCURRENT_UPDATE"
          ? t("staleVersion")
          : error.code === "VALIDATION_ERROR"
            ? t("invalidValue")
            : t("saveFailed");
      setFeedback({ key: variables.setting.key, message });
      void queryClient.invalidateQueries({ queryKey: ["settings"] });
      setDrafts((current) => {
        const next = { ...current };
        delete next[variables.setting.key];
        return next;
      });
    },
  });

  if (settingsQuery.isPending) {
    return (
      <div className="grid gap-3">
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-16 w-full" />
      </div>
    );
  }

  if (!settingsQuery.data?.ok) {
    return (
      <p className="rounded-xl border border-fog bg-canvas p-6 text-sm text-charcoal">
        {t("loadError")}
      </p>
    );
  }

  const settings = settingsQuery.data.data.items;
  const groups: { key: string; keys: string[] }[] = [
    { key: "alerting", keys: ["alerting."] },
    { key: "notifications", keys: ["notifications."] },
    { key: "requests", keys: ["requests."] },
    { key: "dashboard", keys: ["dashboard."] },
    { key: "flags", keys: ["flags."] },
  ];

  return (
    <div className="grid gap-8">
      {groups.map((group) => {
        const groupSettings = settings.filter((setting) =>
          group.keys.some((prefix) => setting.key.startsWith(prefix)),
        );
        if (groupSettings.length === 0) return null;
        return (
          <section
            key={group.key}
            aria-labelledby={`settings-${group.key}`}
            className="rounded-2xl border border-fog bg-canvas p-6 shadow-soft-lift"
          >
            <h2
              id={`settings-${group.key}`}
              className="text-lg font-bold"
            >
              {t(`groups.${group.key}`)}
            </h2>
            <ul className="mt-4 grid gap-4">
              {groupSettings.map((setting) => {
                const draft = drafts[setting.key];
                const raw = draft?.value ?? initialDraft(setting);
                const version = draft?.version ?? setting.version;
                const dirty = draft !== undefined && draft.value !== initialDraft(setting);
                return (
                  <li
                    key={setting.key}
                    className="grid gap-2 border-t border-fog pt-4 first:border-t-0 first:pt-0"
                  >
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                      <p className="font-mono text-sm font-bold text-ink">
                        {setting.key}
                      </p>
                      <span className="text-xs text-graphite">
                        {t("versionLabel", { version })}
                      </span>
                    </div>
                    <p className="text-sm text-charcoal">
                      {settingKeyLocale(setting, locale)}
                    </p>

                    {setting.value_type === "boolean" ? (
                      <div className="flex items-center gap-3">
                        <button
                          type="button"
                          role="switch"
                          aria-checked={raw === "true"}
                          onClick={() =>
                            setDrafts((current) => ({
                              ...current,
                              [setting.key]: {
                                value: raw === "true" ? "false" : "true",
                                version,
                              },
                            }))
                          }
                          className={
                            "relative h-7 w-12 rounded-full transition-colors duration-200 outline-none focus-visible:ring-2 focus-visible:ring-ring/50 motion-reduce:transition-none " +
                            (raw === "true" ? "bg-brand" : "bg-fog")
                          }
                        >
                          <span
                            aria-hidden
                            className={
                              "absolute top-1 size-5 rounded-full bg-white transition-all duration-200 motion-reduce:transition-none " +
                              (raw === "true" ? "start-6" : "start-1")
                            }
                          />
                        </button>
                        <span className="text-sm text-charcoal">
                          {raw === "true" ? t("enabled") : t("disabled")}
                        </span>
                      </div>
                    ) : setting.value_type === "integer" ? (
                      <input
                        type="number"
                        value={raw}
                        onChange={(event) =>
                          setDrafts((current) => ({
                            ...current,
                            [setting.key]: {
                              value: event.target.value,
                              version,
                            },
                          }))
                        }
                        className="h-11 w-32 rounded-md border border-fog bg-canvas px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
                        aria-label={setting.key}
                      />
                    ) : (
                      <textarea
                        value={raw}
                        rows={3}
                        onChange={(event) =>
                          setDrafts((current) => ({
                            ...current,
                            [setting.key]: {
                              value: event.target.value,
                              version,
                            },
                          }))
                        }
                        className="w-full rounded-md border border-fog bg-canvas p-3 font-mono text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
                        aria-label={setting.key}
                      />
                    )}

                    <div className="flex flex-wrap items-center gap-3">
                      <button
                        type="button"
                        disabled={!dirty || save.isPending}
                        onClick={() =>
                          save.mutate({ setting, raw, version })
                        }
                        className="flex h-11 items-center rounded-md bg-brand px-5 text-sm font-bold uppercase tracking-[0.7px] text-white transition-colors duration-200 hover:bg-brand-deep disabled:opacity-50 motion-reduce:transition-none"
                      >
                        {t("save")}
                      </button>
                      {feedback?.key === setting.key ? (
                        <p
                          role="status"
                          className="text-sm font-bold text-charcoal"
                        >
                          {feedback.message}
                        </p>
                      ) : null}
                    </div>
                  </li>
                );
              })}
            </ul>
          </section>
        );
      })}
    </div>
  );
}

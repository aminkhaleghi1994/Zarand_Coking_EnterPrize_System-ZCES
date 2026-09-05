"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, Check } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { notificationApi, type NotificationRecord } from "@/lib/client-api";

import { formatNotificationTimestamp, notificationEventLabel } from "./shared";
import { useNotificationStream } from "./useNotificationStream";

/**
 * Notification inbox (T012): header bell with a live unread badge driven by
 * the SSE stream, opening a newest-first panel with per-event bilingual
 * descriptions, mark-one/mark-all read, skeletons and an empty state.
 * Rendered only for signed-in users — the inbox is personal data.
 */
export function NotificationBell() {
  const t = useTranslations("notifications");
  const locale = useLocale();
  const queryClient = useQueryClient();

  const [open, setOpen] = useState(false);

  useNotificationStream(true);

  const unreadQuery = useQuery({
    queryKey: ["notifications", "unread-count"],
    queryFn: ({ signal }) => notificationApi.unreadCount(signal),
  });
  const unread = unreadQuery.data?.ok ? unreadQuery.data.data.unread : 0;

  const listQuery = useQuery({
    queryKey: ["notifications", "list"],
    queryFn: ({ signal }) => notificationApi.list({ page: 1, pageSize: 20 }, signal),
    enabled: open,
  });
  const items: NotificationRecord[] = listQuery.data?.ok
    ? listQuery.data.data.items
    : [];

  const markRead = useMutation({
    mutationFn: (id: string) => notificationApi.markRead(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  const markAllRead = useMutation({
    mutationFn: () => notificationApi.markAllRead(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, setOpen]);

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-haspopup="dialog"
        aria-label={unread > 0 ? t("unreadCount", { count: unread }) : t("title")}
        className="relative flex h-11 w-11 items-center justify-center rounded-md text-white/80 transition-colors duration-200 hover:text-white motion-reduce:transition-none"
      >
        <Bell className="h-5 w-5" aria-hidden />
        {unread > 0 ? (
          <span
            aria-hidden
            className="absolute end-0.5 top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-bloom-wine px-1 text-[10px] font-bold text-white"
          >
            {unread > 99 ? "99+" : unread}
          </span>
        ) : null}
      </button>

      {open ? (
        <>
          <button
            type="button"
            aria-label={t("closePanel")}
            className="fixed inset-0 z-40 cursor-default"
            onClick={() => setOpen(false)}
          />
          <div
            role="dialog"
            aria-label={t("title")}
            className="absolute end-0 top-[calc(100%+0.5rem)] z-50 w-[min(24rem,calc(100vw-2rem))] rounded-xl border border-fog bg-canvas shadow-floating-modal"
          >
            <div className="flex items-center justify-between gap-2 border-b border-fog px-4 py-2">
              <p className="text-sm font-bold">{t("title")}</p>
              <button
                type="button"
                onClick={() => markAllRead.mutate()}
                disabled={markAllRead.isPending || unread === 0}
                className="flex h-11 items-center rounded-md px-3 text-xs font-bold uppercase tracking-[0.7px] text-charcoal transition-colors duration-200 hover:bg-cloud disabled:opacity-50 motion-reduce:transition-none"
              >
                {t("markAllRead")}
              </button>
            </div>

            <div className="max-h-[min(24rem,60vh)] overflow-y-auto">
              {listQuery.isPending ? (
                <div className="grid gap-2 p-4">
                  <Skeleton className="h-12 w-full" />
                  <Skeleton className="h-12 w-full" />
                  <Skeleton className="h-12 w-full" />
                </div>
              ) : !listQuery.data?.ok ? (
                <p className="p-4 text-sm text-charcoal">{t("loadError")}</p>
              ) : items.length === 0 ? (
                <p className="p-6 text-center text-sm text-graphite">{t("empty")}</p>
              ) : (
                <ul className="divide-y divide-fog">
                  {items.map((item) => {
                    const isUnread = item.read_at === null;
                    return (
                      <li key={item.id} className="flex items-start gap-3 px-4 py-3">
                        <span
                          aria-hidden
                          className={
                            "mt-1.5 h-2 w-2 shrink-0 rounded-full " +
                            (isUnread ? "bg-bloom-wine" : "bg-fog")
                          }
                        />
                        <div className="min-w-0 flex-1">
                          <p
                            className={
                              isUnread
                                ? "text-sm font-bold text-ink"
                                : "text-sm text-charcoal"
                            }
                          >
                            {notificationEventLabel(t, item.event_type)}
                          </p>
                          {typeof item.payload.body === "string" && item.payload.body ? (
                            <p className="mt-0.5 break-words text-xs text-charcoal">
                              {item.payload.body}
                            </p>
                          ) : null}
                          <p className="mt-0.5 text-xs text-graphite">
                            {formatNotificationTimestamp(item.created_at, locale)}
                          </p>
                        </div>
                        {isUnread ? (
                          <button
                            type="button"
                            onClick={() => markRead.mutate(item.id)}
                            disabled={markRead.isPending}
                            aria-label={t("markRead")}
                            title={t("markRead")}
                            className="mt-0.5 flex h-11 w-11 shrink-0 items-center justify-center rounded-md text-charcoal transition-colors duration-200 hover:bg-cloud disabled:opacity-50 motion-reduce:transition-none"
                          >
                            <Check className="h-4 w-4" aria-hidden />
                          </button>
                        ) : null}
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}

"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

/**
 * Live notification stream (T012): opens the SSE feed on mount and
 * invalidates the notification queries whenever a frame arrives, so the
 * bell badge and the open panel refresh within relay latency. EventSource
 * reconnects on its own; anything missed while disconnected is recovered
 * by the refetch. No timeout is set client-side — the keep-alive comments
 * keep intermediaries from closing the connection.
 */
export function useNotificationStream(enabled: boolean) {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!enabled || typeof window === "undefined") return;

    const source = new EventSource("/api/notifications/stream");

    const onNotification = () => {
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
    };

    source.addEventListener("notification", onNotification);

    return () => {
      source.removeEventListener("notification", onNotification);
      source.close();
    };
  }, [enabled, queryClient]);
}

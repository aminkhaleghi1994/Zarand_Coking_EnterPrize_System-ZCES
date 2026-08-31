"use client";

import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";

import { CSRF_COOKIE } from "@/lib/session-cookies";

export function LogoutButton() {
  const t = useTranslations("auth");
  const locale = useLocale();
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  const logout = async () => {
    setBusy(true);
    const csrf = document.cookie
      .split("; ")
      .find((row) => row.startsWith(`${CSRF_COOKIE}=`))
      ?.split("=")[1];
    await fetch("/api/auth/logout", {
      method: "POST",
      headers: csrf ? { "X-CSRF-Token": csrf } : {},
    });
    router.replace(`/${locale}/login`);
    router.refresh();
  };

  return (
    <button
      type="button"
      onClick={logout}
      disabled={busy}
      className="flex h-11 items-center rounded-md px-3 text-sm text-white/80 transition-colors duration-200 hover:text-white disabled:opacity-50"
    >
      {busy ? t("loggingOut") : t("logout")}
    </button>
  );
}

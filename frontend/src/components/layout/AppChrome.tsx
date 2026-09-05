import { useTranslations } from "next-intl";

import { LocaleSwitcher } from "@/components/common/LocaleSwitcher";
import { ThemeToggle } from "@/components/common/ThemeToggle";
import { MobileNav } from "@/components/layout/MobileNav";
import { SidebarNav } from "@/components/layout/SidebarNav";
import { LogoutButton } from "@/features/auth/LogoutButton";
import { NotificationBell } from "@/features/notifications/NotificationPanel";
import { Link } from "@/i18n/navigation";

export type ChromeIdentity = {
  email: string;
  roles: string[];
} | null;

export function AppChrome({
  children,
  identity,
}: {
  children: React.ReactNode;
  identity: ChromeIdentity;
}) {
  const t = useTranslations();

  const brandLockup = (
    <Link href="/" className="flex h-11 items-center gap-2 rounded-md px-1" aria-label={t("app.name")}>
      <ChevronMark />
      <span className="text-lg font-black tracking-tight">{t("app.name")}</span>
    </Link>
  );

  return (
    <div className="flex min-h-dvh flex-col bg-canvas text-ink">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:start-2 focus:z-50 focus:rounded-md focus:bg-canvas focus:px-4 focus:py-2 focus:text-sm focus:font-bold focus:shadow-floating-modal"
      >
        {t("a11y.skipToContent")}
      </a>

      <div className="flex h-9 items-center justify-between gap-4 bg-slab px-4 text-sm text-white md:px-6">
        <span className="hidden truncate text-white/70 md:inline">{t("app.fullName")}</span>
        <div className="flex items-center gap-1">
          <ThemeToggle tone="dark" />
          <LocaleSwitcher tone="dark" />
          {identity ? (
            <span className="flex items-center gap-1">
              <NotificationBell />
              <span className="hidden max-w-48 truncate text-white/90 md:inline" title={identity.email}>
                {identity.email}
              </span>
              {identity.roles.length > 0 && (
                <span className="hidden rounded-lg bg-white/10 px-2 py-0.5 text-xs text-white lg:inline">
                  {identity.roles.join(" · ")}
                </span>
              )}
              <LogoutButton />
            </span>
          ) : (
            <Link
              href="/login"
              className="flex h-11 min-w-11 items-center justify-center px-2 font-bold text-white transition-colors duration-200 hover:text-brand-bright"
            >
              {t("utilityStrip.signIn")}
            </Link>
          )}
        </div>
      </div>

      <div className="flex flex-1">
        <aside className="sticky top-0 hidden h-[calc(100dvh-2.25rem)] w-64 shrink-0 flex-col gap-8 overflow-y-auto border-e border-fog bg-canvas p-4 lg:flex">
          {brandLockup}
          <SidebarNav />
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex h-16 items-center gap-2 border-b border-fog bg-canvas px-4 lg:hidden">
            <MobileNav brand={brandLockup} />
            {brandLockup}
          </header>

          <main id="main-content" className="flex-1 bg-cloud">
            {children}
          </main>

          <footer className="border-t border-fog bg-slab text-white">
            <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-4 text-xs text-white/60 md:px-8">
              <p>{t("footer.legal", { year: new Date().getFullYear() })}</p>
              <p>{t("app.tagline")}</p>
            </div>
          </footer>
        </div>
      </div>
    </div>
  );
}

function ChevronMark() {
  return (
    <span aria-hidden className="flex gap-1">
      <span className="h-5 w-1.5 -skew-x-12 bg-brand rtl:skew-x-12" />
      <span className="h-5 w-1.5 -skew-x-12 bg-brand rtl:skew-x-12" />
    </span>
  );
}

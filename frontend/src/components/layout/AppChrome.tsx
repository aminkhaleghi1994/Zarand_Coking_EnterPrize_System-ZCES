import { useTranslations } from "next-intl";

import { LocaleSwitcher } from "@/components/common/LocaleSwitcher";
import { Link } from "@/i18n/navigation";

const NAV_KEYS = ["dashboard", "employees", "warehouse", "assets", "loans"] as const;

export function AppChrome({ children }: { children: React.ReactNode }) {
  const t = useTranslations();

  return (
    <div className="flex min-h-dvh flex-col bg-canvas text-ink">
      <div className="flex h-9 items-center justify-between bg-ink px-4 text-sm text-white md:px-8">
        <span>{t("utilityStrip.forBusiness")}</span>
        <div className="flex items-center gap-2">
          <LocaleSwitcher />
          <Link
            href="/login"
            className="flex h-11 min-w-11 items-center justify-center px-2 font-bold text-white transition-colors duration-200 hover:text-brand-bright"
          >
            {t("utilityStrip.signIn")}
          </Link>
        </div>
      </div>

      <header className="border-b border-fog bg-canvas">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4 md:px-8">
          <Link href="/" className="flex h-11 items-center gap-2" aria-label={t("app.name")}>
            <span aria-hidden className="text-2xl font-black tracking-tight text-brand">
              {"//"}
            </span>
            <span className="text-lg font-black tracking-tight">{t("app.name")}</span>
          </Link>
          <nav aria-label={t("nav.menu")} className="hidden items-center gap-1 lg:flex">
            {NAV_KEYS.map((key) => (
              <span
                key={key}
                className="rounded-md px-3 py-2 text-sm text-ink/90 transition-colors duration-200 hover:bg-cloud"
              >
                {t(`nav.${key}`)}
              </span>
            ))}
          </nav>
          <Link
            href="/login"
            className="hidden h-11 items-center rounded-md bg-brand px-4 text-sm font-bold uppercase tracking-wide text-white transition-colors duration-200 hover:bg-brand-deep md:inline-flex"
          >
            {t("utilityStrip.signIn")}
          </Link>
        </div>
      </header>

      <main className="flex-1">{children}</main>

      <footer className="bg-ink text-white">
        <div className="mx-auto grid max-w-7xl gap-8 px-4 py-16 md:grid-cols-3 md:px-8">
          <FooterColumn title={t("footer.columns.company")}>
            <FooterLink label={t("footer.links.about")} />
            <FooterLink label={t("footer.links.contact")} />
            <FooterLink label={t("footer.links.careers")} />
          </FooterColumn>
          <FooterColumn title={t("footer.columns.operations")}>
            <FooterLink label={t("footer.links.warehouse")} />
            <FooterLink label={t("footer.links.loans")} />
            <FooterLink label={t("footer.links.assets")} />
          </FooterColumn>
          <FooterColumn title={t("footer.columns.support")}>
            <FooterLink label={t("footer.links.help")} />
            <FooterLink label={t("footer.links.privacy")} />
            <FooterLink label={t("footer.links.terms")} />
          </FooterColumn>
        </div>
        <div className="border-t border-white/10">
          <p className="mx-auto max-w-7xl px-4 py-6 text-xs text-white/60 md:px-8">
            {t("footer.legal", { year: new Date().getFullYear() })}
          </p>
        </div>
      </footer>
    </div>
  );
}

function FooterColumn({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="mb-4 text-sm font-bold uppercase tracking-wide">{title}</h3>
      <ul className="space-y-2 text-sm">{children}</ul>
    </div>
  );
}

function FooterLink({ label }: { label: string }) {
  return (
    <li>
      <span className="inline-flex h-11 items-center text-white/70 transition-colors duration-200 hover:text-white">
        {label}
      </span>
    </li>
  );
}

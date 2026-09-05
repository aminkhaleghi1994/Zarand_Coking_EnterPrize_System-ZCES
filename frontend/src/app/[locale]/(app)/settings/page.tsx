import { getTranslations, setRequestLocale } from "next-intl/server";

import { getSession } from "@/lib/session";
import { SettingsConsole } from "@/features/settings/SettingsConsole";
import { Link } from "@/i18n/navigation";

export default async function SettingsPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("settings");
  const session = await getSession();

  if (!session.ok || !session.session.permissions.includes("settings:setting:read")) {
    return (
      <div className="mx-auto grid max-w-7xl gap-8 px-4 py-8 md:px-8 md:py-12">
        <h1 className="text-3xl font-bold md:text-4xl">{t("title")}</h1>
        <p className="rounded-xl border border-fog bg-canvas p-6 text-charcoal">
          {t("noAccess")}
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto grid max-w-4xl gap-8 px-4 py-8 md:px-8 md:py-12">
      <section className="grid gap-2">
        <span className="text-sm font-bold uppercase tracking-widest text-brand dark:text-brand-bright">
          {t("eyebrow")}
        </span>
        <h1 className="text-3xl font-bold leading-tight md:text-4xl">{t("title")}</h1>
        <p className="text-charcoal">{t("description")}</p>
      </section>
      <SettingsConsole />
      <p className="text-xs text-graphite">
        {t("auditNote")}
        {session.session.permissions.includes("reports:inventory:read") ? (
          <>
            {" "}
            <Link href="/reports" className="font-bold text-brand underline">
              {t("reportsLink")}
            </Link>
          </>
        ) : null}
      </p>
    </div>
  );
}

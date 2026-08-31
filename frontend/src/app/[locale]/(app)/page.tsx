import {
  Banknote,
  ChartColumnBig,
  MonitorSmartphone,
  Settings,
  Users,
  Warehouse,
} from "lucide-react";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { HealthStatusCard } from "@/components/common/HealthStatusCard";
import { getSession } from "@/lib/session";

const MODULES = [
  { key: "employees", icon: Users, phase: 3 },
  { key: "warehouse", icon: Warehouse, phase: 4 },
  { key: "assets", icon: MonitorSmartphone, phase: 6 },
  { key: "loans", icon: Banknote, phase: 7 },
  { key: "reports", icon: ChartColumnBig, phase: 9 },
  { key: "settings", icon: Settings, phase: 9 },
] as const;

export default async function LocalePage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("dashboard");
  const session = await getSession();

  return (
    <div className="mx-auto grid max-w-7xl gap-10 px-4 py-8 md:px-8 md:py-12">
      <section className="grid gap-2">
        <span className="text-sm font-bold uppercase tracking-widest text-brand">
          {t("eyebrow")}
        </span>
        <h1 className="text-3xl font-bold leading-tight md:text-4xl">{t("welcome")}</h1>
        {session.ok && (
          <>
            <p className="text-charcoal">
              {t("identityHint", { email: session.session.user.email })}
            </p>
            {session.session.roles.length > 0 && (
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <span className="text-xs font-bold uppercase tracking-wide text-graphite">
                  {t("rolesLabel")}
                </span>
                {session.session.roles.map((role) => (
                  <span
                    key={role}
                    className="rounded-lg border border-fog bg-canvas px-2 py-1 text-xs font-bold text-charcoal"
                  >
                    {role}
                  </span>
                ))}
              </div>
            )}
          </>
        )}
      </section>

      <section aria-labelledby="status-heading" className="grid gap-4">
        <div className="grid gap-1">
          <h2 id="status-heading" className="text-xl font-bold">
            {t("statusTitle")}
          </h2>
          <p className="text-sm text-graphite">{t("statusDescription")}</p>
        </div>
        <HealthStatusCard />
      </section>

      <section aria-labelledby="modules-heading" className="grid gap-4">
        <div className="grid gap-1">
          <h2 id="modules-heading" className="text-xl font-bold">
            {t("modulesTitle")}
          </h2>
          <p className="text-sm text-graphite">{t("modulesDescription")}</p>
        </div>
        <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {MODULES.map(({ key, icon: Icon, phase }) => (
            <li
              key={key}
              className="flex flex-col gap-3 rounded-xl border border-fog bg-canvas p-6 shadow-soft-lift"
            >
              <span className="flex size-11 items-center justify-center rounded-lg bg-brand-soft text-brand-deep">
                <Icon aria-hidden className="size-6" />
              </span>
              <div className="grid gap-1">
                <h3 className="font-bold">{t(`modules.${key}.title`)}</h3>
                <p className="text-sm text-charcoal">{t(`modules.${key}.description`)}</p>
              </div>
              <span className="mt-auto w-fit rounded-lg border border-fog px-2 py-1 text-xs font-bold text-graphite">
                {t("phaseBadge", { phase })}
              </span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

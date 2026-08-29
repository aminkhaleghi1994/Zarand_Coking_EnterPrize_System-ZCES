import { getTranslations, setRequestLocale } from "next-intl/server";

import { HealthStatusCard } from "@/components/common/HealthStatusCard";
import { Link } from "@/i18n/navigation";

export default async function LocalePage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("home");

  return (
    <div>
      <section className="bg-canvas">
        <div className="mx-auto grid max-w-7xl gap-10 px-4 py-16 md:grid-cols-[1.2fr_1fr] md:px-8 md:py-24">
          <div className="flex flex-col items-start gap-6">
            <span className="text-sm font-bold uppercase tracking-widest text-brand">
              {t("eyebrow")}
            </span>
            <h1 className="text-4xl font-bold leading-tight md:text-5xl">{t("title")}</h1>
            <p className="max-w-xl text-lg text-charcoal">{t("description")}</p>
            <Link
              href="/login"
              className="inline-flex h-11 items-center rounded-md bg-brand px-6 text-sm font-bold uppercase tracking-wide text-white shadow-soft-lift transition-colors duration-200 hover:bg-brand-deep"
            >
              {t("cta")}
            </Link>
          </div>
          <div className="flex items-start justify-start md:justify-end">
            <HealthStatusCard />
          </div>
        </div>
      </section>

      <section className="border-t border-fog bg-cloud">
        <div className="mx-auto max-w-7xl px-4 py-12 md:px-8">
          <p className="text-sm text-graphite">{t("healthDescription")}</p>
        </div>
      </section>
    </div>
  );
}

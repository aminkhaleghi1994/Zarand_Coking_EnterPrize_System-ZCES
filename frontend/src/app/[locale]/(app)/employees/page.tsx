import { getTranslations, setRequestLocale } from "next-intl/server";

import { EmployeeTable } from "@/features/employees/EmployeeTable";

export default async function EmployeesPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("employees");

  return (
    <div className="mx-auto grid max-w-7xl gap-8 px-4 py-8 md:px-8 md:py-12">
      <section className="grid gap-2">
        <span className="text-sm font-bold uppercase tracking-widest text-brand dark:text-brand-bright">
          {t("eyebrow")}
        </span>
        <h1 className="text-3xl font-bold leading-tight md:text-4xl">{t("title")}</h1>
        <p className="text-charcoal">{t("description")}</p>
      </section>
      <EmployeeTable />
    </div>
  );
}

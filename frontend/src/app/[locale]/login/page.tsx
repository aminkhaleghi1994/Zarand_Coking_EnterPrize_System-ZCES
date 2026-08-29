import { getTranslations, setRequestLocale } from "next-intl/server";

import { LoginForm } from "@/features/auth/LoginForm";

export default async function LoginPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("login");

  return (
    <div className="flex min-h-[70dvh] items-center justify-center bg-cloud px-4 py-12">
      <div className="w-full max-w-md rounded-xl bg-canvas p-8 shadow-soft-lift">
        <div className="mb-8 grid gap-2">
          <h1 className="text-2xl font-bold">{t("title")}</h1>
          <p className="text-sm text-charcoal">{t("description")}</p>
        </div>
        <LoginForm />
      </div>
    </div>
  );
}

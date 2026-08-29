import { redirect } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { LoginForm } from "@/features/auth/LoginForm";
import { getSession } from "@/lib/session";

export default async function LoginPage({
  params,
  searchParams,
}: {
  params: Promise<{ locale: string }>;
  searchParams: Promise<{ next?: string; expired?: string }>;
}) {
  const { locale } = await params;
  const { next, expired } = await searchParams;
  setRequestLocale(locale);
  const t = await getTranslations("login");

  const session = await getSession();
  if (session.ok) {
    redirect(next && next.startsWith("/") ? next : `/${locale}`);
  }

  return (
    <div className="flex min-h-[70dvh] items-center justify-center bg-cloud px-4 py-12">
      <div className="w-full max-w-md rounded-xl bg-canvas p-8 shadow-soft-lift">
        <div className="mb-8 grid gap-2">
          <h1 className="text-2xl font-bold">{t("title")}</h1>
          <p className="text-sm text-charcoal">
            {expired ? t("sessionExpired") : t("description")}
          </p>
        </div>
        <LoginForm nextPath={next} />
      </div>
    </div>
  );
}

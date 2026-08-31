import { ArrowLeft, ArrowRight } from "lucide-react";
import { redirect } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { LocaleSwitcher } from "@/components/common/LocaleSwitcher";
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
  const ta = await getTranslations("app");

  const session = await getSession();
  if (session.ok) {
    redirect(next && next.startsWith("/") ? next : `/${locale}`);
  }

  const BackArrow = locale === "fa" ? ArrowRight : ArrowLeft;

  return (
    <div className="grid min-h-dvh lg:grid-cols-[1.1fr_1fr]">
      <div className="relative hidden flex-col justify-between gap-16 overflow-hidden bg-ink p-10 text-white xl:flex 2xl:p-16">
        <div className="flex items-center justify-between">
          <span aria-hidden className="flex gap-2">
            <span className="h-10 w-3 -skew-x-12 bg-brand rtl:skew-x-12" />
            <span className="h-10 w-3 -skew-x-12 bg-brand rtl:skew-x-12" />
          </span>
          <LocaleSwitcher tone="dark" />
        </div>

        <div className="grid max-w-lg gap-4">
          <span className="text-sm font-bold uppercase tracking-widest text-brand-bright">
            {t("secureNote")}
          </span>
          <h1 className="text-4xl font-bold leading-tight">{ta("fullName")}</h1>
          <p className="text-lg text-white/70">{ta("tagline")}</p>
        </div>

        <div
          aria-hidden
          className="pointer-events-none absolute -bottom-24 -end-16 flex gap-4 opacity-10"
        >
          <span className="h-56 w-14 -skew-x-12 bg-brand-bright rtl:skew-x-12" />
          <span className="h-56 w-14 -skew-x-12 bg-brand-bright rtl:skew-x-12" />
        </div>
      </div>

      <div className="flex items-center justify-center bg-canvas px-4 py-12 md:px-8">
        <div className="w-full max-w-md">
          <div className="mb-8 flex items-center justify-between xl:hidden">
            <span aria-hidden className="flex gap-2">
              <span className="h-8 w-2.5 -skew-x-12 bg-brand rtl:skew-x-12" />
              <span className="h-8 w-2.5 -skew-x-12 bg-brand rtl:skew-x-12" />
            </span>
            <LocaleSwitcher />
          </div>

          <div className="mb-8 grid gap-2">
            <h2 className="text-2xl font-bold">{t("title")}</h2>
            <p className="text-sm text-charcoal">
              {expired ? t("sessionExpired") : t("description")}
            </p>
          </div>

          <div className="rounded-xl border border-fog bg-canvas p-6 shadow-soft-lift md:p-8">
            <LoginForm nextPath={next} />
          </div>

          <p className="mt-2 text-center">
            <a
              href={`/${locale}`}
              className="inline-flex h-11 items-center gap-2 text-charcoal transition-colors duration-200 hover:text-brand"
            >
              <BackArrow aria-hidden className="size-4 rtl:-scale-x-100" />
              {t("backHome")}
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}

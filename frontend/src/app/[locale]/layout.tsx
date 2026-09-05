import type { Metadata } from "next";
import Script from "next/script";
import { notFound } from "next/navigation";
import { hasLocale, NextIntlClientProvider } from "next-intl";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { Providers } from "@/components/providers/Providers";
import { kalamehForLocale } from "@/fonts/kalameh";
import { routing } from "@/i18n/routing";
import { THEME_INIT_SCRIPT } from "@/lib/theme";

import "../globals.css";

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "app" });
  return {
    title: t("fullName"),
    description: t("tagline"),
  };
}

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) {
    notFound();
  }
  setRequestLocale(locale);

  const font = kalamehForLocale(locale);
  const direction = locale === "fa" ? "rtl" : "ltr";

  return (
    <html lang={locale} dir={direction} className={font.variable} suppressHydrationWarning>
      <body className="antialiased" suppressHydrationWarning>
        {/* Imperative injection outside React's render tree: the script is
            written into the server HTML pre-paint and never re-created by
            client renders (id-deduplicated), so the React 19
            "Encountered a script tag" warning is structurally impossible. */}
        <Script id="zces-theme-init" strategy="beforeInteractive">
          {THEME_INIT_SCRIPT}
        </Script>
        <NextIntlClientProvider>
          <Providers>{children}</Providers>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}

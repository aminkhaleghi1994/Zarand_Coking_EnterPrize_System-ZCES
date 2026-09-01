import type { Metadata } from "next";
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
        {/* Server-rendered inline script: the browser executes it during the
            initial HTML parse (pre-paint), and hydration never re-creates a
            server-rendered node, so React 19's "Encountered a script tag"
            client-render warning cannot fire. (next/script beforeInteractive
            still routed the node through React's client tree — commit
            8e55e7b's premise did not hold.) */}
        <script id="zces-theme-init" dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
        <NextIntlClientProvider>
          <Providers>{children}</Providers>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}

import createMiddleware from "next-intl/middleware";
import { NextResponse, type NextRequest } from "next/server";

import { routing } from "./i18n/routing";

const handleI18nRouting = createMiddleware(routing);

export default function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const locale = pathname.split("/")[1] === "fa" ? "fa" : routing.defaultLocale;
  const isAuthPage = /^\/(en|fa)\/login\b/.test(pathname);
  const isApiOrAsset =
    pathname.startsWith("/api") || pathname.startsWith("/_next") || pathname.includes(".");

  if (!isAuthPage && !isApiOrAsset && !request.cookies.has("zces_at") && !request.cookies.has("zces_rt")) {
    const url = request.nextUrl.clone();
    url.pathname = `/${locale}/login`;
    url.search = `?next=${encodeURIComponent(pathname)}`;
    return NextResponse.redirect(url);
  }

  return handleI18nRouting(request);
}

export const config = {
  matcher: ["/((?!api|_next|_vercel|.*\\..*).*)"],
};

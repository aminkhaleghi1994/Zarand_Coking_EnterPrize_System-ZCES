import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

const nextConfig: NextConfig = {
  allowedDevOrigins: (process.env.NEXT_DEV_ALLOWED_ORIGINS ?? "127.0.0.1")
    .split(",")
    .map((origin) => origin.trim())
    .filter(Boolean),
};

export default withNextIntl(nextConfig);

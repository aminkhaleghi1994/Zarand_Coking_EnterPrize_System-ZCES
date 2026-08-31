import localFont from "next/font/local";

const standard = localFont({
  src: [
    { path: "./standard/KalamehWeb-Thin.woff2", weight: "100", style: "normal" },
    { path: "./standard/KalamehWeb-Regular.woff2", weight: "400", style: "normal" },
    { path: "./standard/KalamehWeb-Bold.woff2", weight: "700", style: "normal" },
    { path: "./standard/KalamehWeb-Black.woff2", weight: "900", style: "normal" },
  ],
  variable: "--font-kalameh",
  display: "swap",
});

const faNum = localFont({
  src: [
    { path: "./fa-num/KalamehWeb(FaNum)-Thin.woff2", weight: "100", style: "normal" },
    { path: "./fa-num/KalamehWeb(FaNum)-Regular.woff2", weight: "400", style: "normal" },
    { path: "./fa-num/KalamehWeb(FaNum)-Bold.woff2", weight: "700", style: "normal" },
    { path: "./fa-num/KalamehWeb(FaNum)-Black.woff2", weight: "900", style: "normal" },
  ],
  variable: "--font-kalameh",
  display: "swap",
});

export function kalamehForLocale(locale: string) {
  return locale === "fa" ? faNum : standard;
}

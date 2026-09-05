import type { ApiError } from "@/lib/client-api";

type Translator = {
  (key: string): string;
  has?(key: string): boolean;
};

export function warehouseErrorMessage(t: Translator, error: ApiError): string {
  const key = `errors.${error.code}`;
  if (t.has?.(key)) {
    return t(key);
  }
  return t("errors.generic");
}

export function formatWarehouseTimestamp(iso: string, locale: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  return locale === "fa"
    ? date.toLocaleString("fa-IR-u-ca-persian", { hour12: false })
    : date.toLocaleString("en-GB", { hour12: false });
}

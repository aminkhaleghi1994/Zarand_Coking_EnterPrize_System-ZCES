type Translator = {
  (key: string): string;
  has?(key: string): boolean;
};

export function notificationEventLabel(t: Translator, eventType: string): string {
  const key = `events.${eventType}`;
  if (t.has?.(key)) {
    return t(key);
  }
  return t("unknownEvent");
}

export function formatNotificationTimestamp(iso: string, locale: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  return locale === "fa"
    ? date.toLocaleString("fa-IR-u-ca-persian", { hour12: false })
    : date.toLocaleString("en-GB", { hour12: false });
}

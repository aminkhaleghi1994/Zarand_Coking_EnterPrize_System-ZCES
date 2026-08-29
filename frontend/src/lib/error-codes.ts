export const STANDARD_ERROR_CODES = [
  "VALIDATION_ERROR",
  "AUTHENTICATION_REQUIRED",
  "AUTHORIZATION_DENIED",
  "RESOURCE_NOT_FOUND",
  "DUPLICATE_RESOURCE",
  "CONFLICT_CONCURRENT_UPDATE",
  "INSUFFICIENT_STOCK",
  "BUSINESS_RULE_VIOLATION",
  "RATE_LIMITED",
  "INTERNAL_ERROR",
  "STALE_VERSION",
  "RESOURCE_LOCKED",
] as const;

export type StandardErrorCode = (typeof STANDARD_ERROR_CODES)[number];

export function isStandardErrorCode(code: string): code is StandardErrorCode {
  return (STANDARD_ERROR_CODES as readonly string[]).includes(code);
}

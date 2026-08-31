"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useLocale, useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ErrorEnvelopeSchema } from "@/lib/schemas";
import { loginSchema, type LoginValues } from "@/lib/validators";

const STANDARD_ERROR_CODES = [
  "AUTHENTICATION_REQUIRED",
  "VALIDATION_ERROR",
  "INTERNAL_ERROR",
  "RATE_LIMITED",
] as const;

export function LoginForm({ nextPath }: { nextPath?: string }) {
  const t = useTranslations();
  const locale = useLocale();
  const router = useRouter();
  const [submitError, setSubmitError] = useState<string | null>(null);
  const summaryRef = useRef<HTMLDivElement>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    mode: "onBlur",
    defaultValues: { email: "", password: "", remember: false },
  });

  const hasFieldErrors = Object.keys(errors).length > 0;
  const showSummary = submitError !== null || hasFieldErrors;

  useEffect(() => {
    if (submitError !== null) {
      summaryRef.current?.focus();
    }
  }, [submitError]);

  const onSubmit = async (values: LoginValues) => {
    setSubmitError(null);
    const response = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: values.email, password: values.password }),
    });

    if (response.ok) {
      const destination = nextPath && nextPath.startsWith("/") ? nextPath : `/${locale}`;
      router.replace(destination);
      router.refresh();
      return;
    }

    const body: unknown = await response.json().catch(() => null);
    const envelope = ErrorEnvelopeSchema.safeParse(body);
    const code = envelope.success ? envelope.data.code : null;
    setSubmitError(
      code && STANDARD_ERROR_CODES.includes(code as (typeof STANDARD_ERROR_CODES)[number])
        ? t(`errors.codes.${code}`)
        : t("errors.unexpected"),
    );
  };

  return (
    <form
      onSubmit={handleSubmit(onSubmit)}
      noValidate
      className="grid gap-5"
      aria-busy={isSubmitting}
    >
      <div
        ref={summaryRef}
        tabIndex={-1}
        role={showSummary ? "alert" : undefined}
        className="grid gap-1 rounded-md p-1 outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
      >
        {showSummary && (
          <p className="text-sm font-bold text-bloom-deep">
            {submitError ?? t("login.formInvalid")}
          </p>
        )}
      </div>

      <div className="grid gap-2">
        <Label htmlFor="login-email">{t("login.email")}</Label>
        <Input
          id="login-email"
          type="email"
          autoComplete="email"
          placeholder={t("login.emailPlaceholder")}
          className="h-11 rounded-md"
          aria-invalid={errors.email ? "true" : undefined}
          aria-describedby={errors.email ? "login-email-error" : undefined}
          {...register("email")}
        />
        <FieldError id="login-email-error" message={errors.email ? t(errors.email.message as never) : undefined} />
      </div>

      <div className="grid gap-2">
        <Label htmlFor="login-password">{t("login.password")}</Label>
        <Input
          id="login-password"
          type="password"
          autoComplete="current-password"
          placeholder={t("login.passwordPlaceholder")}
          className="h-11 rounded-md"
          aria-invalid={errors.password ? "true" : undefined}
          aria-describedby={errors.password ? "login-password-error" : undefined}
          {...register("password")}
        />
        <FieldError id="login-password-error" message={errors.password ? t(errors.password.message as never) : undefined} />
      </div>

      <Button
        type="submit"
        disabled={isSubmitting}
        className="h-11 w-full rounded-md text-sm font-bold uppercase tracking-wide"
      >
        {isSubmitting ? t("login.submitting") : t("login.submit")}
      </Button>
    </form>
  );
}

function FieldError({ id, message }: { id: string; message?: string }) {
  if (!message) {
    return null;
  }
  return (
    <p id={id} className="text-sm text-bloom-deep">
      {message}
    </p>
  );
}

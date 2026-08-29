"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useLocale, useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ErrorEnvelopeSchema } from "@/lib/schemas";
import { loginSchema, type LoginValues } from "@/lib/validators";

export function LoginForm({ nextPath }: { nextPath?: string }) {
  const t = useTranslations();
  const locale = useLocale();
  const router = useRouter();
  const [submitError, setSubmitError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    mode: "onBlur",
    defaultValues: { email: "", password: "", remember: false },
  });

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
    if (envelope.success) {
      const code = envelope.data.code;
      setSubmitError(
        isStandardError(code) ? t(`errors.codes.${code}`) : t("errors.unexpected"),
      );
    } else {
      setSubmitError(t("errors.unexpected"));
    }
  };

  const isStandardError = (code: string): boolean =>
    code === "AUTHENTICATION_REQUIRED" || code === "VALIDATION_ERROR" ||
    code === "INTERNAL_ERROR" || code === "RATE_LIMITED";

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="grid gap-5">
      <div className="grid gap-2">
        <Label htmlFor="login-email">{t("login.email")}</Label>
        <Input
          id="login-email"
          type="email"
          autoComplete="email"
          placeholder={t("login.emailPlaceholder")}
          className="h-11 rounded-md"
          aria-invalid={errors.email ? "true" : undefined}
          {...register("email")}
        />
        <FieldError message={errors.email ? t(errors.email.message as never) : undefined} />
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
          {...register("password")}
        />
        <FieldError message={errors.password ? t(errors.password.message as never) : undefined} />
      </div>

      <div aria-live="polite" className="min-h-6 text-sm">
        {submitError && <p className="text-bloom-deep">{submitError}</p>}
        {Object.keys(errors).length > 0 && !submitError && (
          <p className="text-bloom-deep">{t("login.formInvalid")}</p>
        )}
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

function FieldError({ message }: { message?: string }) {
  if (!message) {
    return null;
  }
  return <p className="text-sm text-bloom-deep">{message}</p>;
}

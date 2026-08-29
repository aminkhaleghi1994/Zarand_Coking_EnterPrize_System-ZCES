"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { loginSchema, type LoginValues } from "@/lib/validators";

export function LoginForm() {
  const t = useTranslations("login");
  const [submitted, setSubmitted] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting, isValid },
  } = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    mode: "onBlur",
    defaultValues: { email: "", password: "", remember: false },
  });

  const onSubmit = async () => {
    await new Promise((resolve) => setTimeout(resolve, 300));
    setSubmitted(true);
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="grid gap-5">
      <div className="grid gap-2">
        <Label htmlFor="login-email">{t("email")}</Label>
        <Input
          id="login-email"
          type="email"
          autoComplete="email"
          placeholder={t("emailPlaceholder")}
          className="h-11 rounded-md"
          aria-invalid={errors.email ? "true" : undefined}
          {...register("email")}
        />
        <FieldError message={errors.email ? t(errors.email.message as never) : undefined} />
      </div>

      <div className="grid gap-2">
        <Label htmlFor="login-password">{t("password")}</Label>
        <Input
          id="login-password"
          type="password"
          autoComplete="current-password"
          placeholder={t("passwordPlaceholder")}
          className="h-11 rounded-md"
          aria-invalid={errors.password ? "true" : undefined}
          {...register("password")}
        />
        <FieldError message={errors.password ? t(errors.password.message as never) : undefined} />
      </div>

      <div className="flex items-center justify-between gap-4">
        <label className="flex min-h-11 items-center gap-2 text-sm text-charcoal">
          <input
            type="checkbox"
            className="size-4 rounded-sm border-steel accent-[#024ad8]"
            {...register("remember")}
          />
          {t("remember")}
        </label>
        <span className="text-sm text-brand underline-offset-4">{t("forgot")}</span>
      </div>

      <div aria-live="polite" className="min-h-6 text-sm">
        {Object.keys(errors).length > 0 && (
          <p className="text-bloom-deep">{t("formInvalid")}</p>
        )}
        {errors.email === undefined && errors.password === undefined && submitted && (
          <p className="text-brand-deep">{t("phaseNote")}</p>
        )}
      </div>

      <Button
        type="submit"
        disabled={isSubmitting || (!isValid && submitted)}
        className="h-11 w-full rounded-md text-sm font-bold uppercase tracking-wide"
      >
        {isSubmitting ? t("submitting") : t("submit")}
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

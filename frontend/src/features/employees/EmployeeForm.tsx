"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  employeeApi,
  orgApi,
  type ApiError,
  type EmployeeDetail,
  type Workplace,
} from "@/lib/client-api";

const createSchema = z.object({
  national_id: z.string().regex(/^\d{10}$/),
  personnel_code: z.string().min(1).max(50),
  first_name: z.string().min(1).max(100),
  last_name: z.string().min(1).max(100),
  first_name_fa: z.string().max(100).optional().or(z.literal("")),
  last_name_fa: z.string().max(100).optional().or(z.literal("")),
  birth_date: z.string().optional().or(z.literal("")),
  phone: z.string().max(20).optional().or(z.literal("")),
  workplace_id: z.string().uuid(),
  email: z.string().email(),
  username: z.string().min(3).max(100),
  password: z.string().min(8).max(128),
});

const editSchema = createSchema
  .omit({ national_id: true, personnel_code: true, email: true, username: true, password: true })
  .extend({ version: z.number().int().min(1) });

type CreateValues = z.infer<typeof createSchema>;
type EditValues = z.infer<typeof editSchema>;

type FormMode =
  | { kind: "create" }
  | { kind: "edit"; employee: EmployeeDetail };

export function EmployeeForm({
  mode,
  onSaved,
  onCancel,
}: {
  mode: FormMode;
  onSaved: (employee: EmployeeDetail) => void;
  onCancel: () => void;
}) {
  const t = useTranslations("employees");
  const [submitError, setSubmitError] = useState<string | null>(null);

  const workplacesQuery = useQuery({
    queryKey: ["org", "workplaces"],
    queryFn: ({ signal }) => orgApi.workplaces(signal),
  });
  const complexesQuery = useQuery({
    queryKey: ["org", "complexes"],
    queryFn: ({ signal }) => orgApi.complexes(signal),
  });

  const workplaceById = useMemo(() => {
    const map = new Map<string, Workplace>();
    for (const workplace of workplacesQuery.data?.ok ? workplacesQuery.data.data.items : []) {
      map.set(workplace.id, workplace);
    }
    return map;
  }, [workplacesQuery.data]);

  const complexName = useMemo(() => {
    const map = new Map<string, string>();
    for (const complex of complexesQuery.data?.ok ? complexesQuery.data.data.items : []) {
      map.set(complex.id, complex.name);
    }
    return map;
  }, [complexesQuery.data]);

  const isEdit = mode.kind === "edit";
  const schema = isEdit ? editSchema : createSchema;

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<CreateValues | EditValues>({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    resolver: zodResolver(schema as any),
    defaultValues: isEdit
      ? {
          first_name: mode.employee.first_name,
          last_name: mode.employee.last_name,
          first_name_fa: mode.employee.first_name_fa ?? "",
          last_name_fa: mode.employee.last_name_fa ?? "",
          birth_date: mode.employee.birth_date ?? "",
          phone: mode.employee.phone ?? "",
          workplace_id: mode.employee.workplace.id,
          version: mode.employee.version,
        }
      : {
          national_id: "",
          personnel_code: "",
          first_name: "",
          last_name: "",
          first_name_fa: "",
          last_name_fa: "",
          birth_date: "",
          phone: "",
          workplace_id: "",
          email: "",
          username: "",
          password: "",
        },
  });

  useEffect(() => {
    if (submitError) {
      const timer = setTimeout(() => setSubmitError(null), 6000);
      return () => clearTimeout(timer);
    }
  }, [submitError]);

  const onSubmit = async (values: CreateValues | EditValues) => {
    setSubmitError(null);
    if (mode.kind === "create") {
      const create = values as CreateValues;
      const result = await employeeApi.create({
        national_id: create.national_id,
        personnel_code: create.personnel_code,
        first_name: create.first_name,
        last_name: create.last_name,
        first_name_fa: create.first_name_fa || null,
        last_name_fa: create.last_name_fa || null,
        birth_date: create.birth_date || null,
        phone: create.phone || null,
        workplace_id: create.workplace_id,
        user: {
          email: create.email,
          username: create.username,
          password: create.password,
        },
      });
      handleResult(result);
      return;
    }
    const edit = values as EditValues;
    const result = await employeeApi.update(mode.employee.id, {
      first_name: edit.first_name,
      last_name: edit.last_name,
      first_name_fa: edit.first_name_fa || null,
      last_name_fa: edit.last_name_fa || null,
      birth_date: edit.birth_date || null,
      phone: edit.phone || null,
      workplace_id: edit.workplace_id,
      version: edit.version,
    });
    handleResult(result);
  };

  const handleResult = (result: { ok: boolean; error?: ApiError }) => {
    if (result.ok) {
      onSaved((result as { ok: true; data: EmployeeDetail }).data);
      return;
    }
    setSubmitError(t(`errors.${result.error!.code}`, { defaultValue: t("errors.generic") }));
  };

  const fieldError = (name: string): string | undefined => {
    const error = (errors as Record<string, { message?: string }> | undefined)?.[name];
    return error?.message ? t(`validation.${error.message}`, { defaultValue: error.message }) : undefined;
  };

  return (
    <form
      onSubmit={handleSubmit(onSubmit)}
      noValidate
      aria-busy={isSubmitting}
      className="grid gap-6 rounded-xl border border-fog bg-canvas p-6 shadow-soft-lift md:p-8"
    >
      {submitError && (
        <p role="alert" className="rounded-md bg-bloom-wine/10 p-3 text-sm font-bold text-bloom-deep">
          {submitError}
        </p>
      )}

      <section className="grid gap-4">
        <h3 className="text-sm font-bold uppercase tracking-wide text-graphite">
          {t("form.identitySection")}
        </h3>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={t("form.nationalId")} error={fieldError("national_id")}>
            <Input
              type="text"
              inputMode="numeric"
              maxLength={10}
              disabled={isEdit}
              className="h-11 rounded-md disabled:opacity-60"
              aria-invalid={fieldError("national_id") ? "true" : undefined}
              {...register("national_id")}
            />
          </Field>
          <Field label={t("form.personnelCode")} error={fieldError("personnel_code")}>
            <Input
              type="text"
              disabled={isEdit}
              className="h-11 rounded-md disabled:opacity-60"
              aria-invalid={fieldError("personnel_code") ? "true" : undefined}
              {...register("personnel_code")}
            />
          </Field>
          <Field label={t("form.firstName")} error={fieldError("first_name")}>
            <Input type="text" className="h-11 rounded-md" {...register("first_name")} />
          </Field>
          <Field label={t("form.lastName")} error={fieldError("last_name")}>
            <Input type="text" className="h-11 rounded-md" {...register("last_name")} />
          </Field>
          <Field label={t("form.firstNameFa")} error={fieldError("first_name_fa")}>
            <Input type="text" className="h-11 rounded-md" {...register("first_name_fa")} />
          </Field>
          <Field label={t("form.lastNameFa")} error={fieldError("last_name_fa")}>
            <Input type="text" className="h-11 rounded-md" {...register("last_name_fa")} />
          </Field>
          <Field label={t("form.birthDate")} error={fieldError("birth_date")}>
            <Input type="date" className="h-11 rounded-md" {...register("birth_date")} />
          </Field>
          <Field label={t("form.phone")} error={fieldError("phone")}>
            <Input type="tel" dir="ltr" className="h-11 rounded-md" {...register("phone")} />
          </Field>
        </div>
      </section>

      <section className="grid gap-4">
        <h3 className="text-sm font-bold uppercase tracking-wide text-graphite">
          {t("form.assignmentSection")}
        </h3>
        <Field label={t("form.workplace")} error={fieldError("workplace_id")}>
          <select
            className="h-11 rounded-md border border-input bg-canvas px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
            aria-invalid={fieldError("workplace_id") ? "true" : undefined}
            {...register("workplace_id")}
          >
            <option value="">{t("form.workplacePlaceholder")}</option>
            {[...workplaceById.values()].map((workplace) => (
              <option key={workplace.id} value={workplace.id}>
                {complexName.get(workplace.complex_id) ?? workplace.complex_id} — {workplace.name}
              </option>
            ))}
          </select>
        </Field>
      </section>

      {!isEdit && (
        <section className="grid gap-4">
          <h3 className="text-sm font-bold uppercase tracking-wide text-graphite">
            {t("form.accountSection")}
          </h3>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t("form.email")} error={fieldError("email")}>
              <Input
                type="email"
                dir="ltr"
                autoComplete="off"
                className="h-11 rounded-md"
                {...register("email")}
              />
            </Field>
            <Field label={t("form.username")} error={fieldError("username")}>
              <Input
                type="text"
                dir="ltr"
                autoComplete="off"
                className="h-11 rounded-md"
                {...register("username")}
              />
            </Field>
            <Field label={t("form.password")} error={fieldError("password")}>
              <Input
                type="password"
                autoComplete="new-password"
                className="h-11 rounded-md"
                {...register("password")}
              />
            </Field>
          </div>
        </section>
      )}

      <div className="flex flex-wrap gap-3">
        <Button type="submit" disabled={isSubmitting} className="h-11 rounded-md px-6">
          {isSubmitting ? t("form.saving") : t("form.save")}
        </Button>
        <Button
          type="button"
          variant="outline"
          onClick={onCancel}
          className="h-11 rounded-md px-6"
        >
          {t("form.cancel")}
        </Button>
      </div>
    </form>
  );
}

function Field({
  label,
  error,
  children,
}: {
  label: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="grid gap-2">
      <Label className="text-sm font-bold">{label}</Label>
      {children}
      {error && (
        <p className="text-sm text-bloom-deep" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

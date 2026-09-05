import { z } from "zod";

import { isStandardErrorCode } from "./error-codes";

export const ComponentStatusSchema = z.object({
  status: z.enum(["up", "down"]),
  latency_ms: z.number().int().nonnegative().nullable().optional(),
});

export const HealthStatusSchema = z.object({
  status: z.literal("ok"),
  app: z.string(),
  env: z.string(),
  version: z.string(),
  components: z.record(z.string(), ComponentStatusSchema),
});

export type HealthStatus = z.infer<typeof HealthStatusSchema>;
export type ComponentStatus = z.infer<typeof ComponentStatusSchema>;

export const ErrorEnvelopeSchema = z.object({
  code: z.string().refine(isStandardErrorCode, { message: "unknown error code" }).or(z.string()),
  message: z.string(),
  details: z.unknown().nullable().optional(),
  trace_id: z.string(),
});

export type ErrorEnvelope = z.infer<typeof ErrorEnvelopeSchema>;

export const SessionUserSchema = z.object({
  id: z.string(),
  email: z.string(),
  username: z.string(),
  is_active: z.boolean(),
});

export const ScopeAssignmentSchema = z.object({
  id: z.string(),
  level: z.enum(["global", "complex", "workplace"]),
  module: z.string(),
  resource: z.string(),
  operation: z.string(),
  complex_id: z.string().nullable().optional(),
  workplace_id: z.string().nullable().optional(),
});

export const MeSchema = z.object({
  user: SessionUserSchema,
  roles: z.array(z.string()),
  permissions: z.array(z.string()),
  scopes: z.array(ScopeAssignmentSchema),
});

export type Me = z.infer<typeof MeSchema>;

export const TokenPairSchema = z.object({
  user: SessionUserSchema,
  roles: z.array(z.string()),
  access_token: z.string(),
  access_expires_in: z.number().int().positive(),
  refresh_token: z.string(),
});

export type TokenPair = z.infer<typeof TokenPairSchema>;

export const LoginResponseSchema = z.object({
  user: SessionUserSchema,
  roles: z.array(z.string()),
});

export const LoginInputSchema = z.object({
  email: z.email("login.errors.emailInvalid"),
  password: z.string().min(8, "login.errors.passwordShort"),
});

export const WarehouseItemInputSchema = z.object({
  name: z
    .string()
    .trim()
    .min(1, "warehouse.validation.nameRequired")
    .max(200, "warehouse.validation.nameRequired"),
  name_fa: z
    .string()
    .trim()
    .min(1, "warehouse.validation.nameFaRequired")
    .max(200, "warehouse.validation.nameFaRequired"),
  code: z
    .string()
    .trim()
    .max(50, "warehouse.validation.codeTooLong")
    .optional()
    .nullable(),
  unit: z
    .string()
    .trim()
    .min(1, "warehouse.validation.unitRequired")
    .max(30, "warehouse.validation.unitRequired"),
  min_quantity: z.string().regex(/^\d+(\.\d{1,3})?$/, "warehouse.validation.minQuantityInvalid"),
  description: z
    .string()
    .max(1000, "warehouse.validation.descriptionTooLong")
    .optional()
    .nullable(),
});

export type WarehouseItemInput = z.infer<typeof WarehouseItemInputSchema>;

export const RequestInputSchema = z.object({
  purpose_description: z
    .string()
    .trim()
    .min(1, "requests.validation.purposeRequired")
    .max(2000, "requests.validation.purposeTooLong"),
  lines: z
    .array(
      z.object({
        item_id: z.string().min(1, "requests.validation.itemRequired"),
        quantity: z
          .string()
          .regex(/^\d+(\.\d{1,3})?$/, "requests.validation.quantityInvalid"),
        note: z.string().max(500, "requests.validation.noteTooLong").optional().nullable(),
      }),
    )
    .min(1, "requests.validation.linesRequired"),
});

export type RequestInput = z.infer<typeof RequestInputSchema>;

export const AssetInputSchema = z.object({
  name: z
    .string()
    .trim()
    .min(1, "assets.validation.nameRequired")
    .max(200, "assets.validation.nameRequired"),
  name_fa: z
    .string()
    .trim()
    .min(1, "assets.validation.nameFaRequired")
    .max(200, "assets.validation.nameFaRequired"),
  serial: z
    .string()
    .trim()
    .min(1, "assets.validation.serialRequired")
    .max(100, "assets.validation.serialRequired"),
  description: z
    .string()
    .max(1000, "assets.validation.descriptionTooLong")
    .optional()
    .nullable(),
});

export type AssetInput = z.infer<typeof AssetInputSchema>;

export const AssetAssignInputSchema = z
  .object({
    target_type: z.enum(["employee", "location"]),
    employee_id: z.string().optional().nullable(),
    location: z.string().trim().max(200).optional().nullable(),
    note: z.string().max(500, "assets.validation.noteTooLong").optional().nullable(),
  })
  .refine(
    (value) =>
      value.target_type === "employee"
        ? Boolean(value.employee_id)
        : Boolean(value.location && value.location.length > 0),
    {
      message: "assets.validation.employeeRequired",
      path: ["employee_id"],
    },
  );

export type AssetAssignInput = z.infer<typeof AssetAssignInputSchema>;

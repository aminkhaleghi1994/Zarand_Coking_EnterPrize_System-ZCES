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

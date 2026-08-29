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

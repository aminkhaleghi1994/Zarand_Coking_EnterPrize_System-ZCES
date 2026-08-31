import { z } from "zod";

export const loginSchema = z.object({
  email: z.string().min(1, "login.errors.emailRequired").email("login.errors.emailInvalid"),
  password: z.string().min(8, "login.errors.passwordShort"),
  remember: z.boolean(),
});

export type LoginValues = z.infer<typeof loginSchema>;

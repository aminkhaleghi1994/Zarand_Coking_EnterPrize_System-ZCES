import { CSRF_COOKIE } from "@/lib/session-cookies";

export type ApiError = { code: string; message: string; traceId?: string };

export type ApiResult<T> = { ok: true; data: T } | { ok: false; error: ApiError };

export type Page<T> = { items: T[]; page: number; page_size: number; total: number };

export type Complex = { id: string; code: string; name: string; name_fa: string; company_id: string };

export type Workplace = {
  id: string;
  code: string;
  name: string;
  name_fa: string;
  complex_id: string;
};

export type EmployeeSummary = {
  id: string;
  national_id: string;
  personnel_code: string;
  first_name: string;
  last_name: string;
  is_active: boolean;
  workplace_id: string;
  workplace_name: string;
};

export type EmployeeDetail = {
  id: string;
  version: number;
  national_id: string;
  personnel_code: string;
  first_name: string;
  last_name: string;
  first_name_fa: string | null;
  last_name_fa: string | null;
  birth_date: string | null;
  phone: string | null;
  is_active: boolean;
  workplace: { id: string; code: string; name: string; name_fa: string; complex_id: string };
  complex: { id: string; code: string; name: string; name_fa: string };
  user: { id: string; email: string; username: string; is_active: boolean };
  created_at: string;
};

export type Role = { id: string; name: string; description: string | null };
export type Permission = { id: string; code: string; name_en: string; name_fa: string };
export type AdminUser = { id: string; email: string; username: string; is_active: boolean };
export type ScopeAssignment = {
  id: string;
  level: "global" | "complex" | "workplace";
  module: string;
  resource: string;
  operation: string;
  complex_id: string | null;
  workplace_id: string | null;
};

function readCsrfToken(): string | null {
  if (typeof document === "undefined") return null;
  return (
    document.cookie
      .split("; ")
      .find((row) => row.startsWith(`${CSRF_COOKIE}=`))
      ?.split("=")[1] ?? null
  );
}

export async function bffFetch<T>(
  path: string,
  init?: { method?: "GET" | "POST" | "PATCH" | "DELETE"; body?: unknown; signal?: AbortSignal },
): Promise<ApiResult<T>> {
  const method = init?.method ?? "GET";
  const headers: Record<string, string> = {};
  const csrf = readCsrfToken();
  if (method !== "GET" && csrf) {
    headers["X-CSRF-Token"] = csrf;
  }
  if (init?.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  let response: Response;
  try {
    response = await fetch(path, {
      method,
      headers,
      cache: "no-store",
      signal: init?.signal,
      ...(init?.body !== undefined ? { body: JSON.stringify(init.body) } : {}),
    });
  } catch {
    return { ok: false, error: { code: "INTERNAL_ERROR", message: "Network error" } };
  }

  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const envelope = body as { code?: string; message?: string; trace_id?: string } | null;
    return {
      ok: false,
      error: {
        code: envelope?.code ?? "INTERNAL_ERROR",
        message: envelope?.message ?? "Unexpected error",
        traceId: envelope?.trace_id,
      },
    };
  }
  return { ok: true, data: body as T };
}

export type EmployeeListParams = {
  page?: number;
  pageSize?: number;
  search?: string;
  status?: "active" | "deactivated" | "all";
  workplaceId?: string;
  complexId?: string;
};

function listQuery(params: EmployeeListParams): string {
  const query = new URLSearchParams();
  if (params.page) query.set("page", String(params.page));
  if (params.pageSize) query.set("page_size", String(params.pageSize));
  if (params.search) query.set("search", params.search);
  if (params.status) query.set("status", params.status);
  if (params.workplaceId) query.set("workplace_id", params.workplaceId);
  if (params.complexId) query.set("complex_id", params.complexId);
  const raw = query.toString();
  return raw ? `?${raw}` : "";
}

export const employeeApi = {
  list: (params: EmployeeListParams, signal?: AbortSignal) =>
    bffFetch<Page<EmployeeSummary>>(`/api/employees${listQuery(params)}`, { signal }),
  get: (id: string) => bffFetch<EmployeeDetail>(`/api/employees/${id}`),
  create: (payload: unknown) => bffFetch<EmployeeDetail>("/api/employees", { method: "POST", body: payload }),
  update: (id: string, payload: unknown) =>
    bffFetch<EmployeeDetail>(`/api/employees/${id}`, { method: "PATCH", body: payload }),
  deactivate: (id: string, version: number | undefined) =>
    bffFetch<EmployeeDetail>(`/api/employees/${id}/deactivate`, {
      method: "POST",
      body: version ? { version } : {},
    }),
  reactivate: (id: string) =>
    bffFetch<EmployeeDetail>(`/api/employees/${id}/reactivate`, { method: "POST", body: {} }),
};

export const orgApi = {
  complexes: (signal?: AbortSignal) =>
    bffFetch<Page<Complex>>("/api/org/complexes?page_size=100", { signal }),
  workplaces: (signal?: AbortSignal) =>
    bffFetch<Page<Workplace>>("/api/org/workplaces?page_size=100", { signal }),
};

export const adminApi = {
  roles: (signal?: AbortSignal) => bffFetch<Page<Role>>("/api/admin/roles?page_size=100", { signal }),
  createRole: (name: string, description?: string) =>
    bffFetch<Role>("/api/admin/roles", { method: "POST", body: { name, description } }),
  permissions: (signal?: AbortSignal) =>
    bffFetch<Page<Permission>>("/api/admin/permissions?page_size=200", { signal }),
  users: (signal?: AbortSignal) =>
    bffFetch<Page<AdminUser>>("/api/admin/users?page_size=100", { signal }),
  userRoles: (userId: string, signal?: AbortSignal) =>
    bffFetch<{ role_ids: string[] }>(`/api/admin/users/${userId}/roles`, { signal }),
  userScopes: (userId: string, signal?: AbortSignal) =>
    bffFetch<{ items: ScopeAssignment[] }>(`/api/admin/users/${userId}/scopes`, { signal }),
  assignRole: (userId: string, roleId: string) =>
    bffFetch<{ success: boolean }>(`/api/admin/users/${userId}/roles`, {
      method: "POST",
      body: { role_id: roleId },
    }),
  revokeRole: (userId: string, roleId: string) =>
    bffFetch<{ success: boolean }>(`/api/admin/users/${userId}/roles/${roleId}`, {
      method: "DELETE",
    }),
  assignScope: (userId: string, payload: unknown) =>
    bffFetch<ScopeAssignment>(`/api/admin/users/${userId}/scopes`, {
      method: "POST",
      body: payload,
    }),
  revokeScope: (userId: string, assignmentId: string) =>
    bffFetch<{ success: boolean }>(`/api/admin/users/${userId}/scopes/${assignmentId}`, {
      method: "DELETE",
    }),
  setPassword: (userId: string, password: string) =>
    bffFetch<{ success: boolean }>(`/api/users/${userId}/password`, {
      method: "POST",
      body: { password },
    }),
};

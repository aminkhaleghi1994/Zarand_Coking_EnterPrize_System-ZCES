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

export type WarehouseItem = {
  id: string;
  version: number;
  name: string;
  name_fa: string;
  code: string | null;
  unit: string;
  min_quantity: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
};

export type Warehouse = {
  id: string;
  version: number;
  workplace_id: string;
  code: string;
  name: string;
  name_fa: string;
  is_active: boolean;
  created_at: string;
};

export type WarehouseShelf = {
  id: string;
  version: number;
  warehouse_id: string;
  code: string;
  name: string | null;
  name_fa: string | null;
  is_active: boolean;
  created_at: string;
};

export type ItemBrief = {
  id: string;
  name: string;
  name_fa: string;
  code: string | null;
  unit: string;
  min_quantity: string;
};

export type ShelfBrief = { id: string; code: string; name: string | null };
export type WarehouseBrief = { id: string; code: string; name: string };

export type Placement = {
  id: string;
  item: ItemBrief;
  shelf: ShelfBrief;
  warehouse: WarehouseBrief;
  quantity: string;
  below_min_threshold: boolean;
};

export type Movement = {
  id: string;
  movement_type: "receive" | "issue" | "adjust";
  quantity_delta: string;
  resulting_quantity: string;
  reason: string | null;
  actor_user_id: string | null;
  created_at: string;
};

export type StockAlert = {
  id: string;
  placement_id: string;
  item: ItemBrief;
  shelf: ShelfBrief;
  warehouse: WarehouseBrief;
  quantity_at_alert: string;
  threshold_at_alert: string;
  current_quantity: string;
  raised_at: string;
  resolved_at: string | null;
};

export type RequestLine = {
  id: string;
  item: ItemBrief;
  quantity: string;
  note: string | null;
};

export type RequestRecord = {
  id: string;
  version: number;
  status: "pending" | "approved" | "rejected" | "fulfilled";
  requested_by: string;
  requested_by_email: string | null;
  purpose_description: string;
  decision_note: string | null;
  decided_by: string | null;
  decided_at: string | null;
  fulfilled_at: string | null;
  lines: RequestLine[];
  created_at: string;
};

export type MePayload = {
  user: { id: string; email: string; username: string; is_active: boolean };
  roles: string[];
  permissions: string[];
  scopes: ScopeAssignment[];
};

export type WarehouseListParams = {
  page?: number;
  pageSize?: number;
  search?: string;
  workplaceId?: string;
  itemId?: string;
  includeEmpty?: boolean;
};

function warehouseQuery(params: WarehouseListParams): string {
  const query = new URLSearchParams();
  if (params.page) query.set("page", String(params.page));
  if (params.pageSize) query.set("page_size", String(params.pageSize));
  if (params.search) query.set("search", params.search);
  if (params.workplaceId) query.set("workplace_id", params.workplaceId);
  if (params.itemId) query.set("item_id", params.itemId);
  if (params.includeEmpty) query.set("include_empty", "true");
  const raw = query.toString();
  return raw ? `?${raw}` : "";
}

export const warehouseApi = {
  items: {
    search: (search: string, signal?: AbortSignal) =>
      bffFetch<Page<WarehouseItem>>(
        `/api/warehouse/items${warehouseQuery({ search, pageSize: 20 })}`,
        { signal },
      ),
    list: (params: WarehouseListParams, signal?: AbortSignal) =>
      bffFetch<Page<WarehouseItem>>(`/api/warehouse/items${warehouseQuery(params)}`, { signal }),
    create: (payload: unknown) =>
      bffFetch<WarehouseItem>("/api/warehouse/items", { method: "POST", body: payload }),
    update: (id: string, payload: unknown) =>
      bffFetch<WarehouseItem>(`/api/warehouse/items/${id}`, { method: "PATCH", body: payload }),
    retire: (id: string, version: number) =>
      bffFetch<WarehouseItem>(`/api/warehouse/items/${id}/retire`, {
        method: "POST",
        body: { version },
      }),
  },
  warehouses: {
    list: (params: WarehouseListParams, signal?: AbortSignal) =>
      bffFetch<Page<Warehouse>>(`/api/warehouse/warehouses${warehouseQuery(params)}`, { signal }),
    create: (payload: unknown) =>
      bffFetch<Warehouse>("/api/warehouse/warehouses", { method: "POST", body: payload }),
    update: (id: string, payload: unknown) =>
      bffFetch<Warehouse>(`/api/warehouse/warehouses/${id}`, { method: "PATCH", body: payload }),
    retire: (id: string, version: number) =>
      bffFetch<Warehouse>(`/api/warehouse/warehouses/${id}/retire`, {
        method: "POST",
        body: { version },
      }),
    shelves: (warehouseId: string, signal?: AbortSignal) =>
      bffFetch<Page<WarehouseShelf>>(
        `/api/warehouse/warehouses/${warehouseId}/shelves?page_size=100`,
        { signal },
      ),
    createShelf: (warehouseId: string, payload: unknown) =>
      bffFetch<WarehouseShelf>(`/api/warehouse/warehouses/${warehouseId}/shelves`, {
        method: "POST",
        body: payload,
      }),
    updateShelf: (shelfId: string, payload: unknown) =>
      bffFetch<WarehouseShelf>(`/api/warehouse/shelves/${shelfId}`, {
        method: "PATCH",
        body: payload,
      }),
    retireShelf: (shelfId: string, version: number) =>
      bffFetch<WarehouseShelf>(`/api/warehouse/shelves/${shelfId}/retire`, {
        method: "POST",
        body: { version },
      }),
  },
  placements: {
    list: (params: WarehouseListParams, signal?: AbortSignal) =>
      bffFetch<Page<Placement>>(`/api/warehouse/placements${warehouseQuery(params)}`, { signal }),
    receive: (payload: unknown) =>
      bffFetch<Placement>("/api/warehouse/placements/receive", { method: "POST", body: payload }),
    issue: (payload: unknown) =>
      bffFetch<Placement>("/api/warehouse/placements/issue", { method: "POST", body: payload }),
    adjust: (payload: unknown) =>
      bffFetch<Placement>("/api/warehouse/placements/adjust", { method: "POST", body: payload }),
    movements: (placementId: string, signal?: AbortSignal) =>
      bffFetch<Page<Movement>>(`/api/warehouse/placements/${placementId}/movements?page_size=50`, {
        signal,
      }),
  },
  alerts: {
    list: (status: "true" | "false" | "all", signal?: AbortSignal) =>
      bffFetch<Page<StockAlert>>(`/api/warehouse/alerts?active=${status}&page_size=50`, { signal }),
  },
  me: (signal?: AbortSignal) => bffFetch<MePayload>("/api/auth/me", { signal }),
};

export const requestApi = {
  list: (
    status: "all" | "pending" | "approved" | "rejected" | "fulfilled",
    signal?: AbortSignal,
  ) =>
    bffFetch<Page<RequestRecord>>(`/api/warehouse/requests?status=${status}&page_size=50`, {
      signal,
    }),
  get: (id: string, signal?: AbortSignal) =>
    bffFetch<RequestRecord>(`/api/warehouse/requests/${id}`, { signal }),
  create: (payload: unknown) =>
    bffFetch<RequestRecord>("/api/warehouse/requests", { method: "POST", body: payload }),
  approve: (id: string, version: number, note?: string) =>
    bffFetch<RequestRecord>(`/api/warehouse/requests/${id}/approve`, {
      method: "POST",
      body: { version, note: note || null },
    }),
  reject: (id: string, version: number, note?: string) =>
    bffFetch<RequestRecord>(`/api/warehouse/requests/${id}/reject`, {
      method: "POST",
      body: { version, note: note || null },
    }),
  fulfill: (id: string, version: number, lines: { line_id: string; placement_id: string }[]) =>
    bffFetch<RequestRecord>(`/api/warehouse/requests/${id}/fulfill`, {
      method: "POST",
      body: { version, lines },
    }),
};

"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  adminApi,
  orgApi,
  type ApiError,
  type AdminUser,
  type Role,
  type ScopeAssignment,
} from "@/lib/client-api";
import { cn } from "@/lib/utils";

type Tab = "roles" | "permissions" | "users";

export function AdminViews() {
  const t = useTranslations("admin");
  const [tab, setTab] = useState<Tab>("roles");

  return (
    <div className="grid gap-6">
      <div role="tablist" aria-label={t("tabsLabel")} className="flex flex-wrap gap-1">
        {(["roles", "permissions", "users"] as Tab[]).map((value) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={tab === value}
            onClick={() => setTab(value)}
            className={cn(
              "flex h-11 items-center rounded-md px-5 text-sm outline-none transition-colors duration-200 focus-visible:ring-2 focus-visible:ring-ring/50",
              tab === value
                ? "bg-brand-soft font-bold text-brand-deep dark:text-brand-bright"
                : "text-charcoal hover:bg-cloud",
            )}
          >
            {t(`tabs.${value}`)}
          </button>
        ))}
      </div>

      {tab === "roles" && <RolesPanel />}
      {tab === "permissions" && <PermissionsPanel />}
      {tab === "users" && <UsersPanel />}
    </div>
  );
}

function PanelShell({
  isPending,
  isError,
  children,
}: {
  isPending: boolean;
  isError: boolean;
  children: React.ReactNode;
}) {
  const t = useTranslations("employees");
  if (isPending) {
    return (
      <div className="grid gap-3 rounded-xl border border-fog bg-canvas p-6 shadow-soft-lift">
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-8 w-3/4" />
        <Skeleton className="h-8 w-1/2" />
      </div>
    );
  }
  if (isError) {
    return (
      <div className="rounded-xl border border-fog bg-canvas p-6 shadow-soft-lift">
        <p className="text-sm font-bold text-bloom-deep">{t("errors.generic")}</p>
      </div>
    );
  }
  return <div className="rounded-xl border border-fog bg-canvas p-6 shadow-soft-lift">{children}</div>;
}

function RolesPanel() {
  const t = useTranslations("admin");
  const queryClient = useQueryClient();
  const rolesQuery = useQuery({
    queryKey: ["admin", "roles"],
    queryFn: ({ signal }) => adminApi.roles(signal),
  });
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () => adminApi.createRole(name),
    onSuccess: () => {
      setName("");
      setError(null);
      void queryClient.invalidateQueries({ queryKey: ["admin", "roles"] });
    },
    onError: (mutationError: ApiError) => setError(mutationError.message),
  });

  const roles = rolesQuery.data?.ok ? rolesQuery.data.data.items : [];

  return (
    <PanelShell isPending={rolesQuery.isPending} isError={rolesQuery.isError}>
      <div className="grid gap-4">
        <h3 className="text-sm font-bold uppercase tracking-wide text-graphite">
          {t("roles.createTitle")}
        </h3>
        <div className="flex flex-wrap gap-3">
          <Input
            type="text"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder={t("roles.namePlaceholder")}
            className="h-11 w-full max-w-xs rounded-md"
          />
          <Button
            type="button"
            onClick={() => create.mutate()}
            disabled={name.trim().length < 2 || create.isPending}
            className="h-11 rounded-md px-6"
          >
            {t("roles.create")}
          </Button>
        </div>
        {error && (
          <p role="alert" className="text-sm font-bold text-bloom-deep">
            {error}
          </p>
        )}
        <ul className="grid gap-2">
          {roles.map((role: Role) => (
            <li
              key={role.id}
              className="flex items-center justify-between rounded-lg border border-fog p-3"
            >
              <span className="font-bold">{role.name}</span>
              <span className="text-sm text-graphite">{role.description}</span>
            </li>
          ))}
        </ul>
      </div>
    </PanelShell>
  );
}

function PermissionsPanel() {
  const permissionsQuery = useQuery({
    queryKey: ["admin", "permissions"],
    queryFn: ({ signal }) => adminApi.permissions(signal),
  });
  const permissions = permissionsQuery.data?.ok ? permissionsQuery.data.data.items : [];

  return (
    <PanelShell isPending={permissionsQuery.isPending} isError={permissionsQuery.isError}>
      <ul className="grid gap-2">
        {permissions.map((permission) => (
          <li key={permission.id} className="rounded-lg border border-fog p-3">
            <p className="font-bold" dir="ltr">
              {permission.code}
            </p>
            <p className="text-sm text-charcoal">
              {permission.name_en} — {permission.name_fa}
            </p>
          </li>
        ))}
      </ul>
    </PanelShell>
  );
}

function UsersPanel() {
  const t = useTranslations("admin");
  const usersQuery = useQuery({
    queryKey: ["admin", "users"],
    queryFn: ({ signal }) => adminApi.users(signal),
  });
  const [selected, setSelected] = useState<AdminUser | null>(null);

  const users = usersQuery.data?.ok ? usersQuery.data.data.items : [];

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <PanelShell isPending={usersQuery.isPending} isError={usersQuery.isError}>
        <ul className="grid gap-2">
          {users.map((user) => (
            <li key={user.id}>
              <button
                type="button"
                onClick={() => setSelected(user)}
                aria-pressed={selected?.id === user.id}
                className={cn(
                  "flex w-full flex-col items-start gap-1 rounded-lg border p-3 text-start outline-none transition-colors duration-200 focus-visible:ring-2 focus-visible:ring-ring/50",
                  selected?.id === user.id
                    ? "border-brand bg-brand-soft/50"
                    : "border-fog hover:bg-cloud",
                )}
              >
                <span className="font-bold" dir="ltr">
                  {user.email}
                </span>
                <span className="text-xs text-graphite" dir="ltr">
                  {user.username} · {user.is_active ? t("user.active") : t("user.inactive")}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </PanelShell>

      {selected ? (
        <UserAccessManager user={selected} />
      ) : (
        <div className="rounded-xl border border-dashed border-fog bg-canvas p-6">
          <p className="text-sm text-charcoal">{t("user.pickPrompt")}</p>
        </div>
      )}
    </div>
  );
}

function UserAccessManager({ user }: { user: AdminUser }) {
  const t = useTranslations("admin");
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [scopeLevel, setScopeLevel] = useState<"global" | "complex" | "workplace">("global");
  const [scopeUnitId, setScopeUnitId] = useState("");
  const [scopeTarget, setScopeTarget] = useState("");

  const rolesQuery = useQuery({
    queryKey: ["admin", "roles"],
    queryFn: ({ signal }) => adminApi.roles(signal),
  });
  const userRolesQuery = useQuery({
    queryKey: ["admin", "users", user.id, "roles"],
    queryFn: ({ signal }) => adminApi.userRoles(user.id, signal),
  });
  const userScopesQuery = useQuery({
    queryKey: ["admin", "users", user.id, "scopes"],
    queryFn: ({ signal }) => adminApi.userScopes(user.id, signal),
  });

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["admin", "users", user.id] });
  };

  const assignRole = useMutation({
    mutationFn: (roleId: string) => adminApi.assignRole(user.id, roleId),
    onSuccess: () => {
      setError(null);
      invalidate();
    },
    onError: (mutationError: ApiError) => setError(mutationError.message),
  });
  const revokeRole = useMutation({
    mutationFn: (roleId: string) => adminApi.revokeRole(user.id, roleId),
    onSuccess: () => {
      setError(null);
      invalidate();
    },
    onError: (mutationError: ApiError) => setError(mutationError.message),
  });
  const assignScope = useMutation({
    mutationFn: (payload: unknown) => adminApi.assignScope(user.id, payload),
    onSuccess: () => {
      setError(null);
      invalidate();
    },
    onError: (mutationError: ApiError) => setError(mutationError.message),
  });
  const revokeScope = useMutation({
    mutationFn: (assignmentId: string) => adminApi.revokeScope(user.id, assignmentId),
    onSuccess: () => {
      setError(null);
      invalidate();
    },
    onError: (mutationError: ApiError) => setError(mutationError.message),
  });

  const roles = rolesQuery.data?.ok ? rolesQuery.data.data.items : [];
  const assignedRoleIds = userRolesQuery.data?.ok ? userRolesQuery.data.data.role_ids : [];
  const scopes = userScopesQuery.data?.ok ? userScopesQuery.data.data.items : [];
  const needsUnit = scopeLevel !== "global";
  const parsedTarget = scopeTarget.split(":");

  const submitScope = () => {
    if (parsedTarget.length !== 3 || parsedTarget.some((part) => part.length === 0)) {
      setError(t("scope.invalidTarget"));
      return;
    }
    assignScope.mutate({
      level: scopeLevel,
      module: parsedTarget[0],
      resource: parsedTarget[1],
      operation: parsedTarget[2],
      complex_id: scopeLevel === "complex" ? scopeUnitId : null,
      workplace_id: scopeLevel === "workplace" ? scopeUnitId : null,
    });
  };

  return (
    <div className="grid gap-6 rounded-xl border border-fog bg-canvas p-6 shadow-soft-lift">
      <h3 className="text-lg font-bold" dir="ltr">
        {user.email}
      </h3>
      {error && (
        <p role="alert" className="text-sm font-bold text-bloom-deep">
          {error}
        </p>
      )}

      <section className="grid gap-3">
        <h4 className="text-sm font-bold uppercase tracking-wide text-graphite">
          {t("roles.title")}
        </h4>
        <ul className="grid gap-2">
          {roles.map((role) => {
            const assigned = assignedRoleIds.includes(role.id);
            return (
              <li key={role.id} className="flex items-center justify-between rounded-lg border border-fog p-3">
                <span className="font-bold">{role.name}</span>
                {assigned ? (
                  <button
                    type="button"
                    onClick={() => revokeRole.mutate(role.id)}
                    disabled={revokeRole.isPending}
                    className="flex h-9 items-center rounded-md border border-fog px-3 text-xs font-bold text-bloom-deep hover:bg-bloom-deep/10"
                  >
                    {t("roles.revoke")}
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => assignRole.mutate(role.id)}
                    disabled={assignRole.isPending}
                    className="flex h-9 items-center rounded-md border border-fog px-3 text-xs font-bold text-charcoal hover:bg-cloud hover:text-ink"
                  >
                    {t("roles.assign")}
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      </section>

      <section className="grid gap-3">
        <h4 className="text-sm font-bold uppercase tracking-wide text-graphite">
          {t("scope.title")}
        </h4>
        <div className="grid gap-3 sm:grid-cols-3">
          <select
            aria-label={t("scope.level")}
            value={scopeLevel}
            onChange={(event) => {
              setScopeLevel(event.target.value as typeof scopeLevel);
              setScopeUnitId("");
            }}
            className="h-11 rounded-md border border-input bg-canvas px-3 text-sm"
          >
            <option value="global">{t("scope.global")}</option>
            <option value="complex">{t("scope.complex")}</option>
            <option value="workplace">{t("scope.workplace")}</option>
          </select>
          {needsUnit && <ScopeUnitPicker level={scopeLevel} value={scopeUnitId} onChange={setScopeUnitId} />}
          <Input
            type="text"
            dir="ltr"
            placeholder={t("scope.targetPlaceholder")}
            value={scopeTarget}
            onChange={(event) => setScopeTarget(event.target.value)}
            className="h-11 rounded-md"
          />
        </div>
        <Button type="button" onClick={submitScope} className="h-11 w-fit rounded-md px-6">
          {t("scope.assign")}
        </Button>
        <ul className="grid gap-2">
          {scopes.map((assignment: ScopeAssignment) => (
            <li
              key={assignment.id}
              className="flex items-center justify-between rounded-lg border border-fog p-3"
            >
              <span className="text-sm" dir="ltr">
                {assignment.level}:{assignment.module}:{assignment.resource}:{assignment.operation}
              </span>
              <button
                type="button"
                onClick={() => revokeScope.mutate(assignment.id)}
                disabled={revokeScope.isPending}
                className="flex h-9 items-center rounded-md border border-fog px-3 text-xs font-bold text-bloom-deep hover:bg-bloom-deep/10"
              >
                {t("scope.remove")}
              </button>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function ScopeUnitPicker({
  level,
  value,
  onChange,
}: {
  level: "complex" | "workplace";
  value: string;
  onChange: (value: string) => void;
}) {
  const complexesQuery = useQuery({
    queryKey: ["org", "complexes"],
    queryFn: ({ signal }) => orgApi.complexes(signal),
  });
  const workplacesQuery = useQuery({
    queryKey: ["org", "workplaces"],
    queryFn: ({ signal }) => orgApi.workplaces(signal),
  });

  if (level === "complex") {
    const complexes = complexesQuery.data?.ok ? complexesQuery.data.data.items : [];
    return (
      <select
        aria-label="Complex"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-11 rounded-md border border-input bg-canvas px-3 text-sm"
      >
        <option value="">—</option>
        {complexes.map((complex) => (
          <option key={complex.id} value={complex.id}>
            {complex.name}
          </option>
        ))}
      </select>
    );
  }
  const workplaces = workplacesQuery.data?.ok ? workplacesQuery.data.data.items : [];
  return (
    <select
      aria-label="Workplace"
      value={value}
      onChange={(event) => onChange(event.target.value)}
      className="h-11 rounded-md border border-input bg-canvas px-3 text-sm"
    >
      <option value="">—</option>
      {workplaces.map((workplace) => (
        <option key={workplace.id} value={workplace.id}>
          {workplace.name}
        </option>
      ))}
    </select>
  );
}

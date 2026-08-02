export const PERMISSIONS = [
  "leads.view",
  "leads.edit",
  "leads.delete",
  "deals.view",
  "deals.edit",
  "users.manage",
  "billing.manage",
  "settings.manage",
] as const;

export type PermissionKey = (typeof PERMISSIONS)[number];

export const ROLES = ["owner", "admin", "manager", "employee", "viewer"] as const;
export type OrgRoleKey = (typeof ROLES)[number];

export const PERMISSION_LABELS: Record<PermissionKey, string> = {
  "leads.view": "View Leads",
  "leads.edit": "Edit Leads",
  "leads.delete": "Delete Leads",
  "deals.view": "View Deals",
  "deals.edit": "Edit Deals",
  "users.manage": "Manage Users",
  "billing.manage": "Billing",
  "settings.manage": "Settings",
};

/** Canonical role → permission matrix (mirrors DB seed). */
export const ROLE_PERMISSIONS: Record<OrgRoleKey, readonly PermissionKey[]> = {
  owner: PERMISSIONS,
  admin: [
    "leads.view",
    "leads.edit",
    "leads.delete",
    "deals.view",
    "deals.edit",
    "users.manage",
    "settings.manage",
  ],
  manager: [
    "leads.view",
    "leads.edit",
    "leads.delete",
    "deals.view",
    "deals.edit",
    "settings.manage",
  ],
  employee: ["leads.view", "leads.edit", "deals.view", "deals.edit"],
  viewer: ["leads.view", "deals.view"],
};

export function hasPermission(
  granted: readonly string[] | undefined,
  required: PermissionKey | PermissionKey[],
): boolean {
  const need = Array.isArray(required) ? required : [required];
  const set = new Set(granted || []);
  return need.every((key) => set.has(key));
}

export function hasAnyPermission(
  granted: readonly string[] | undefined,
  required: PermissionKey[],
): boolean {
  const set = new Set(granted || []);
  return required.some((key) => set.has(key));
}

export function isPermissionKey(value: string): value is PermissionKey {
  return (PERMISSIONS as readonly string[]).includes(value);
}

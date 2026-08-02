import type { OrgRoleKey, PermissionKey } from "@/lib/authz/permissions";

export type { OrgRoleKey, PermissionKey };

export type TenantTable =
  | "leads"
  | "deals"
  | "contacts"
  | "files"
  | "organization_settings"
  | "offer_queue"
  | "audit_logs"
  | "organization_members";

export type Organization = {
  id: string;
  name: string;
  slug: string;
};

export type Membership = {
  id: string;
  organization_id: string;
  user_id: string;
  role_id: string;
  status: "active" | "invited" | "suspended";
  roles?: { key: OrgRoleKey; name: string } | null;
};

export type OrgContext = {
  userId: string;
  email: string;
  organizationId: string;
  organization: Organization;
  membership: Membership;
  permissions: PermissionKey[];
};

export type PermissionKey =
  | "org.manage"
  | "members.manage"
  | "leads.read"
  | "leads.write"
  | "deals.read"
  | "deals.write"
  | "contacts.read"
  | "contacts.write"
  | "files.read"
  | "files.write"
  | "settings.read"
  | "settings.write"
  | "sms.send"
  | "audit.read";

export type TenantTable =
  | "leads"
  | "deals"
  | "contacts"
  | "files"
  | "organization_settings"
  | "offer_queue"
  | "audit_logs"
  | "organization_members";

export type OrgRoleKey = "owner" | "admin" | "agent" | "viewer";

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

import { redirect } from "next/navigation";
import type { User } from "@supabase/supabase-js";
import { createClient } from "@/lib/supabase/server";
import { logger } from "@/lib/logger";
import type {
  Membership,
  OrgContext,
  Organization,
  OrgRoleKey,
  PermissionKey,
} from "./types";

export async function getOrgContext(): Promise<OrgContext | null> {
  const supabase = await createClient();
  const {
    data: { user },
    error: userError,
  } = await supabase.auth.getUser();

  if (userError) {
    logger.warn({ err: userError.message }, "getOrgContext auth error");
  }
  if (!user) return null;

  const { data: profile } = await supabase
    .from("profiles")
    .select("current_organization_id, email, full_name")
    .eq("id", user.id)
    .maybeSingle();

  let organizationId = profile?.current_organization_id ?? null;

  if (!organizationId) {
    const { data: memberships } = await supabase
      .from("organization_members")
      .select("organization_id")
      .eq("user_id", user.id)
      .eq("status", "active")
      .limit(1);
    organizationId = memberships?.[0]?.organization_id ?? null;
  }

  if (!organizationId) {
    logger.warn({ userId: user.id }, "user has no organization membership");
    return null;
  }

  const [{ data: organization }, { data: membership }] = await Promise.all([
    supabase
      .from("organizations")
      .select("id, name, slug")
      .eq("id", organizationId)
      .maybeSingle(),
    supabase
      .from("organization_members")
      .select("id, organization_id, user_id, role_id, status")
      .eq("organization_id", organizationId)
      .eq("user_id", user.id)
      .eq("status", "active")
      .maybeSingle(),
  ]);

  if (!organization || !membership) {
    logger.warn({ userId: user.id, organizationId }, "org context incomplete");
    return null;
  }

  const { data: role } = await supabase
    .from("roles")
    .select("key, name")
    .eq("id", membership.role_id)
    .maybeSingle();

  const normalizedMembership: Membership = {
    id: membership.id,
    organization_id: membership.organization_id,
    user_id: membership.user_id,
    role_id: membership.role_id,
    status: membership.status as Membership["status"],
    roles: role ? { key: role.key as OrgRoleKey, name: role.name } : null,
  };

  const permissions = await loadPermissions(supabase, membership.role_id);

  return {
    userId: user.id,
    email: profile?.email || user.email || "",
    organizationId: organization.id,
    organization: organization as Organization,
    membership: normalizedMembership,
    permissions,
  };
}

async function loadPermissions(
  supabase: Awaited<ReturnType<typeof createClient>>,
  roleId?: string,
): Promise<PermissionKey[]> {
  if (!roleId) return [];
  const { data, error } = await supabase
    .from("role_permissions")
    .select("permission_id")
    .eq("role_id", roleId);
  if (error) {
    logger.warn({ err: error.message, roleId }, "loadPermissions failed");
    return [];
  }
  const permissionIds = (data || []).map((row) => row.permission_id);
  if (!permissionIds.length) return [];

  const { data: permissions, error: permErr } = await supabase
    .from("permissions")
    .select("key")
    .in("id", permissionIds);
  if (permErr) {
    logger.warn({ err: permErr.message, roleId }, "loadPermissionKeys failed");
    return [];
  }
  return (permissions || [])
    .map((row) => row.key)
    .filter((key): key is PermissionKey => Boolean(key));
}

export async function requireOrgContext(): Promise<
  OrgContext & { supabase: Awaited<ReturnType<typeof createClient>>; user: User }
> {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const ctx = await getOrgContext();
  if (!ctx) {
    redirect("/login?error=no_organization");
  }
  return { ...ctx, supabase, user };
}

export function assertPermission(ctx: OrgContext, permission: PermissionKey) {
  if (!ctx.permissions.includes(permission)) {
    const err = new Error(`Missing permission: ${permission}`);
    (err as Error & { status: number }).status = 403;
    throw err;
  }
}

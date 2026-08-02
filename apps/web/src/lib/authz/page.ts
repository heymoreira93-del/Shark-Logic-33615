import { redirect } from "next/navigation";
import { requireOrgContext, type OrgContext } from "@/lib/tenant";
import { createClient } from "@/lib/supabase/server";
import { hasAnyPermission, hasPermission, type PermissionKey } from "./permissions";

export type PageAuth = OrgContext & {
  supabase: Awaited<ReturnType<typeof createClient>>;
};

/** Require login + org. Optionally require one/all permissions. */
export async function requirePageAuth(
  permission?: PermissionKey | PermissionKey[],
  options?: { anyOf?: boolean },
): Promise<PageAuth> {
  const ctx = await requireOrgContext();

  if (!permission) return ctx;

  const ok = options?.anyOf
    ? hasAnyPermission(ctx.permissions, Array.isArray(permission) ? permission : [permission])
    : hasPermission(ctx.permissions, permission);

  if (!ok) {
    redirect("/dashboard/unauthorized");
  }
  return ctx;
}

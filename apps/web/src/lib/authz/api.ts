import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { getOrgContext, type OrgContext } from "@/lib/tenant";
import { logger } from "@/lib/logger";
import { AuthError, forbidden, unauthorized } from "./errors";
import { hasPermission, type PermissionKey } from "./permissions";

type Authed = OrgContext & {
  supabase: Awaited<ReturnType<typeof createClient>>;
};

/**
 * Authenticate + authorize an API route.
 * On failure throws AuthError — use withAuth() / denyResponse() so no data leaks.
 */
export async function requireApiAuth(
  permission?: PermissionKey | PermissionKey[],
): Promise<Authed> {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) throw unauthorized();

  const ctx = await getOrgContext();
  if (!ctx) throw unauthorized("No organization membership");

  if (permission && !hasPermission(ctx.permissions, permission)) {
    const first = Array.isArray(permission) ? permission[0] : permission;
    logger.warn(
      {
        userId: ctx.userId,
        orgId: ctx.organizationId,
        permission,
        granted: ctx.permissions,
      },
      "api_forbidden",
    );
    throw forbidden(first);
  }

  return { ...ctx, supabase };
}

/** JSON error with NO data payload. */
export function denyResponse(err: unknown) {
  if (err instanceof AuthError) {
    return NextResponse.json(
      { error: err.message, code: err.code },
      { status: err.status },
    );
  }
  logger.error(
    { err: err instanceof Error ? err.message : String(err) },
    "api_unhandled",
  );
  return NextResponse.json({ error: "Bad request", code: "BAD_REQUEST" }, { status: 400 });
}

export async function withAuth<T>(
  permission: PermissionKey | PermissionKey[] | undefined,
  handler: (ctx: Authed) => Promise<T>,
): Promise<T | NextResponse> {
  try {
    const ctx = await requireApiAuth(permission);
    return await handler(ctx);
  } catch (err) {
    return denyResponse(err);
  }
}

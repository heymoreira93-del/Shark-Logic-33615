import { NextResponse } from "next/server";
import { logError } from "@/lib/logger";
import { denyResponse, requireApiAuth } from "@/lib/authz";
import { tenantFrom } from "@/lib/tenant";

export async function GET() {
  try {
    const ctx = await requireApiAuth("users.manage");
    const { data, error } = await tenantFrom(
      ctx.supabase,
      "organization_members",
      ctx.organizationId,
    )
      .select("id, user_id, status, created_at, role_id")
      .order("created_at", { ascending: true });

    if (error) {
      logError(error, { route: "GET /api/members" });
      return NextResponse.json({ error: "Failed to load members" }, { status: 500 });
    }

    const members = (data || []) as Array<{
      id: string;
      user_id: string;
      status: string;
      created_at: string;
      role_id: string;
    }>;
    const roleIds = [...new Set(members.map((m) => m.role_id))];
    const { data: roles } = roleIds.length
      ? await ctx.supabase.from("roles").select("id, key, name").in("id", roleIds)
      : { data: [] as Array<{ id: string; key: string; name: string }> };
    const roleMap = new Map((roles || []).map((r) => [r.id, r]));

    return NextResponse.json({
      organizationId: ctx.organizationId,
      members: members.map((m) => ({
        ...m,
        role: roleMap.get(m.role_id) || null,
      })),
    });
  } catch (err) {
    return denyResponse(err);
  }
}

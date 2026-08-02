import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { logError } from "@/lib/logger";
import { getOrgContext, tenantFrom } from "@/lib/tenant";

export async function GET() {
  try {
    const supabase = await createClient();
    const ctx = await getOrgContext();
    if (!ctx) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

    const { data, error } = await tenantFrom(
      supabase,
      "organization_members",
      ctx.organizationId,
    )
      .select("id, user_id, status, created_at, role_id")
      .order("created_at", { ascending: true });

    if (error) {
      logError(error, { route: "GET /api/members" });
      return NextResponse.json({ error: error.message }, { status: 500 });
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
      ? await supabase.from("roles").select("id, key, name").in("id", roleIds)
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
    const status = (err as { status?: number }).status || 400;
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Bad request" },
      { status },
    );
  }
}

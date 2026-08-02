import { NextResponse } from "next/server";
import { z } from "zod";
import { createClient } from "@/lib/supabase/server";
import { logError, logger } from "@/lib/logger";
import { assertPermission, getOrgContext, tenantFrom } from "@/lib/tenant";

const schema = z.object({
  assignor_name: z.string().min(1).optional(),
  default_assignment_fee: z.number().nonnegative().optional(),
  default_emd: z.number().nonnegative().optional(),
  notify_phone: z.string().optional(),
  timezone: z.string().optional(),
});

export async function GET() {
  try {
    const supabase = await createClient();
    const ctx = await getOrgContext();
    if (!ctx) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    assertPermission(ctx, "settings.read");

    const { data, error } = await tenantFrom(
      supabase,
      "organization_settings",
      ctx.organizationId,
    )
      .select("*")
      .maybeSingle();

    if (error) {
      logError(error, { route: "GET /api/settings" });
      return NextResponse.json({ error: error.message }, { status: 500 });
    }
    return NextResponse.json({
      organizationId: ctx.organizationId,
      organization: ctx.organization,
      settings: data,
      permissions: ctx.permissions,
    });
  } catch (err) {
    const status = (err as { status?: number }).status || 400;
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Bad request" },
      { status },
    );
  }
}

export async function PATCH(request: Request) {
  try {
    const supabase = await createClient();
    const ctx = await getOrgContext();
    if (!ctx) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    assertPermission(ctx, "settings.write");

    const body = schema.parse(await request.json());
    const { data, error } = await tenantFrom(
      supabase,
      "organization_settings",
      ctx.organizationId,
    )
      .update(body)
      .select("*")
      .single();

    if (error) {
      logError(error, { route: "PATCH /api/settings" });
      return NextResponse.json({ error: error.message }, { status: 500 });
    }

    logger.info({ userId: ctx.userId, orgId: ctx.organizationId }, "settings_updated");
    return NextResponse.json({ settings: data, organizationId: ctx.organizationId });
  } catch (err) {
    logError(err, { route: "PATCH /api/settings" });
    const status = (err as { status?: number }).status || 400;
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Bad request" },
      { status },
    );
  }
}

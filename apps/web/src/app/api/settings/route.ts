import { NextResponse } from "next/server";
import { z } from "zod";
import { logError, logger } from "@/lib/logger";
import { denyResponse, requireApiAuth } from "@/lib/authz";
import { tenantFrom } from "@/lib/tenant";

const schema = z.object({
  assignor_name: z.string().min(1).optional(),
  default_assignment_fee: z.number().nonnegative().optional(),
  default_emd: z.number().nonnegative().optional(),
  notify_phone: z.string().optional(),
  timezone: z.string().optional(),
});

export async function GET() {
  try {
    const ctx = await requireApiAuth("settings.manage");
    const { data, error } = await tenantFrom(
      ctx.supabase,
      "organization_settings",
      ctx.organizationId,
    )
      .select("*")
      .maybeSingle();

    if (error) {
      logError(error, { route: "GET /api/settings" });
      return NextResponse.json({ error: "Failed to load settings" }, { status: 500 });
    }
    return NextResponse.json({
      organizationId: ctx.organizationId,
      organization: ctx.organization,
      settings: data,
    });
  } catch (err) {
    return denyResponse(err);
  }
}

export async function PATCH(request: Request) {
  try {
    const ctx = await requireApiAuth("settings.manage");
    const body = schema.parse(await request.json());
    const { data, error } = await tenantFrom(
      ctx.supabase,
      "organization_settings",
      ctx.organizationId,
    )
      .update(body)
      .select("*")
      .single();

    if (error) {
      logError(error, { route: "PATCH /api/settings" });
      return NextResponse.json({ error: "Failed to update settings" }, { status: 500 });
    }

    logger.info({ userId: ctx.userId, orgId: ctx.organizationId }, "settings_updated");
    return NextResponse.json({ settings: data, organizationId: ctx.organizationId });
  } catch (err) {
    return denyResponse(err);
  }
}

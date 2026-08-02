import { NextResponse } from "next/server";
import { z } from "zod";
import { createClient } from "@/lib/supabase/server";
import { logError, logger } from "@/lib/logger";
import { assertPermission, getOrgContext, tenantFrom } from "@/lib/tenant";

const schema = z.object({
  address: z.string().min(3),
  zip_code: z.string().optional(),
  arv: z.number().optional(),
  mao: z.number().optional(),
  wholesale_fee: z.number().optional(),
  status: z.string().optional(),
  seller_name: z.string().optional(),
  seller_phone: z.string().optional(),
  contact_id: z.string().uuid().optional(),
});

export async function GET() {
  try {
    const supabase = await createClient();
    const ctx = await getOrgContext();
    if (!ctx) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    assertPermission(ctx, "leads.read");

    const { data, error } = await tenantFrom(supabase, "leads", ctx.organizationId)
      .select("id, address, seller_name, seller_phone, arv, mao, status, created_at")
      .order("created_at", { ascending: false })
      .limit(100);

    if (error) {
      logError(error, { route: "GET /api/leads" });
      return NextResponse.json({ error: error.message }, { status: 500 });
    }
    return NextResponse.json({ organizationId: ctx.organizationId, leads: data || [] });
  } catch (err) {
    const status = (err as { status?: number }).status || 400;
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Bad request" },
      { status },
    );
  }
}

export async function POST(request: Request) {
  try {
    const supabase = await createClient();
    const ctx = await getOrgContext();
    if (!ctx) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    assertPermission(ctx, "leads.write");

    const body = schema.parse(await request.json());
    const { data, error } = await tenantFrom(supabase, "leads", ctx.organizationId)
      .insert({
        address: body.address,
        zip_code: body.zip_code || "",
        arv: body.arv ?? 0,
        mao: body.mao ?? 0,
        wholesale_fee: body.wholesale_fee ?? 10000,
        status: body.status || "New Lead",
        seller_name: body.seller_name || "",
        seller_phone: body.seller_phone || "",
        contact_id: body.contact_id || null,
        created_by: ctx.userId,
      })
      .select("id")
      .single();

    if (error) {
      logError(error, { route: "POST /api/leads" });
      return NextResponse.json({ error: error.message }, { status: 500 });
    }

    await tenantFrom(supabase, "audit_logs", ctx.organizationId).insert({
      actor_user_id: ctx.userId,
      action: "lead.created",
      entity_type: "lead",
      entity_id: data.id,
    });

    logger.info(
      { userId: ctx.userId, orgId: ctx.organizationId, leadId: data.id },
      "lead_created",
    );
    return NextResponse.json({ id: data.id, organizationId: ctx.organizationId });
  } catch (err) {
    logError(err, { route: "POST /api/leads" });
    const status = (err as { status?: number }).status || 400;
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Bad request" },
      { status },
    );
  }
}

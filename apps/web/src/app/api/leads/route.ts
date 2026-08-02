import { NextResponse } from "next/server";
import { z } from "zod";
import { logError, logger } from "@/lib/logger";
import { denyResponse, requireApiAuth } from "@/lib/authz";
import { tenantFrom } from "@/lib/tenant";

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
    const ctx = await requireApiAuth("leads.view");
    const { data, error } = await tenantFrom(ctx.supabase, "leads", ctx.organizationId)
      .select("id, address, seller_name, seller_phone, arv, mao, status, created_at")
      .order("created_at", { ascending: false })
      .limit(100);

    if (error) {
      logError(error, { route: "GET /api/leads" });
      return NextResponse.json({ error: "Failed to load leads" }, { status: 500 });
    }
    return NextResponse.json({ organizationId: ctx.organizationId, leads: data || [] });
  } catch (err) {
    return denyResponse(err);
  }
}

export async function POST(request: Request) {
  try {
    const ctx = await requireApiAuth("leads.edit");
    const body = schema.parse(await request.json());
    const { data, error } = await tenantFrom(ctx.supabase, "leads", ctx.organizationId)
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
      return NextResponse.json({ error: "Failed to create lead" }, { status: 500 });
    }

    await tenantFrom(ctx.supabase, "audit_logs", ctx.organizationId).insert({
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
    return denyResponse(err);
  }
}

export async function DELETE(request: Request) {
  try {
    const ctx = await requireApiAuth("leads.delete");
    const id = new URL(request.url).searchParams.get("id");
    if (!id) return NextResponse.json({ error: "id required" }, { status: 400 });

    const { error } = await tenantFrom(ctx.supabase, "leads", ctx.organizationId)
      .delete()
      .eq("id", id);

    if (error) {
      logError(error, { route: "DELETE /api/leads" });
      return NextResponse.json({ error: "Failed to delete lead" }, { status: 500 });
    }

    await tenantFrom(ctx.supabase, "audit_logs", ctx.organizationId).insert({
      actor_user_id: ctx.userId,
      action: "lead.deleted",
      entity_type: "lead",
      entity_id: id,
    });

    return NextResponse.json({ ok: true });
  } catch (err) {
    return denyResponse(err);
  }
}

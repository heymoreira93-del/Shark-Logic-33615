import { NextResponse } from "next/server";
import { z } from "zod";
import { logError, logger } from "@/lib/logger";
import { denyResponse, requireApiAuth } from "@/lib/authz";
import { tenantFrom } from "@/lib/tenant";

const schema = z.object({
  address: z.string().min(3),
  seller_name: z.string().min(1),
  seller_phone: z.string().optional(),
  buyer_name: z.string().optional(),
  price: z.number().nonnegative(),
  deal_kind: z.enum(["purchase", "assignment"]).default("purchase"),
  assignment_fee: z.number().optional(),
  emd: z.number().optional(),
  lead_id: z.string().uuid().optional(),
  contact_id: z.string().uuid().optional(),
});

export async function GET() {
  try {
    const ctx = await requireApiAuth("deals.view");
    const { data, error } = await tenantFrom(ctx.supabase, "deals", ctx.organizationId)
      .select(
        "id, address, seller_name, buyer_name, price, status, deal_kind, sign_token, emd_paid, created_at",
      )
      .order("created_at", { ascending: false })
      .limit(100);

    if (error) {
      logError(error, { route: "GET /api/deals" });
      return NextResponse.json({ error: "Failed to load deals" }, { status: 500 });
    }
    return NextResponse.json({ organizationId: ctx.organizationId, deals: data || [] });
  } catch (err) {
    return denyResponse(err);
  }
}

export async function POST(request: Request) {
  try {
    const ctx = await requireApiAuth("deals.edit");
    const body = schema.parse(await request.json());
    const { data, error } = await tenantFrom(ctx.supabase, "deals", ctx.organizationId)
      .insert({
        lead_id: body.lead_id || null,
        contact_id: body.contact_id || null,
        address: body.address,
        seller_name: body.seller_name,
        seller_phone: body.seller_phone || "",
        buyer_name: body.buyer_name || "",
        price: body.price,
        deal_kind: body.deal_kind,
        assignment_fee: body.assignment_fee ?? 0,
        emd: body.emd ?? Number(process.env.STRIPE_EMD_DOLLARS || 2500),
        created_by: ctx.userId,
      })
      .select(
        "id, address, seller_name, buyer_name, price, status, deal_kind, sign_token, emd_paid, created_at, organization_id",
      )
      .single();

    if (error) {
      logError(error, { route: "POST /api/deals" });
      return NextResponse.json({ error: "Failed to create deal" }, { status: 500 });
    }

    await tenantFrom(ctx.supabase, "audit_logs", ctx.organizationId).insert({
      actor_user_id: ctx.userId,
      action: "deal.created",
      entity_type: "deal",
      entity_id: data.id,
    });

    logger.info(
      { userId: ctx.userId, orgId: ctx.organizationId, dealId: data.id },
      "deal_created",
    );
    return NextResponse.json({ deal: data, organizationId: ctx.organizationId });
  } catch (err) {
    return denyResponse(err);
  }
}

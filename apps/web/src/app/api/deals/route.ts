import { NextResponse } from "next/server";
import { z } from "zod";
import { createClient } from "@/lib/supabase/server";
import { logError, logger } from "@/lib/logger";
import { assertPermission, getOrgContext, tenantFrom } from "@/lib/tenant";

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
    const supabase = await createClient();
    const ctx = await getOrgContext();
    if (!ctx) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    assertPermission(ctx, "deals.read");

    const { data, error } = await tenantFrom(supabase, "deals", ctx.organizationId)
      .select(
        "id, address, seller_name, buyer_name, price, status, deal_kind, sign_token, emd_paid, created_at",
      )
      .order("created_at", { ascending: false })
      .limit(100);

    if (error) {
      logError(error, { route: "GET /api/deals" });
      return NextResponse.json({ error: error.message }, { status: 500 });
    }
    return NextResponse.json({ organizationId: ctx.organizationId, deals: data || [] });
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
    assertPermission(ctx, "deals.write");

    const body = schema.parse(await request.json());
    const { data, error } = await tenantFrom(supabase, "deals", ctx.organizationId)
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
      return NextResponse.json({ error: error.message }, { status: 500 });
    }

    await tenantFrom(supabase, "audit_logs", ctx.organizationId).insert({
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
    logError(err, { route: "POST /api/deals" });
    const status = (err as { status?: number }).status || 400;
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Bad request" },
      { status },
    );
  }
}

import { NextResponse } from "next/server";
import { z } from "zod";
import { logError, logger } from "@/lib/logger";
import { denyResponse, requireApiAuth } from "@/lib/authz";
import { tenantFrom } from "@/lib/tenant";

const schema = z.object({
  kind: z.enum(["seller", "buyer", "agent", "title", "other"]).default("seller"),
  full_name: z.string().min(1),
  email: z.string().email().optional().or(z.literal("")),
  phone: z.string().optional(),
  company_name: z.string().optional(),
  notes: z.string().optional(),
});

export async function GET() {
  try {
    const ctx = await requireApiAuth("leads.view");
    const { data, error } = await tenantFrom(ctx.supabase, "contacts", ctx.organizationId)
      .select("id, kind, full_name, email, phone, company_name, notes, created_at")
      .order("created_at", { ascending: false })
      .limit(200);

    if (error) {
      logError(error, { route: "GET /api/contacts" });
      return NextResponse.json({ error: "Failed to load contacts" }, { status: 500 });
    }
    return NextResponse.json({ organizationId: ctx.organizationId, contacts: data || [] });
  } catch (err) {
    return denyResponse(err);
  }
}

export async function POST(request: Request) {
  try {
    const ctx = await requireApiAuth("leads.edit");
    const body = schema.parse(await request.json());
    const { data, error } = await tenantFrom(ctx.supabase, "contacts", ctx.organizationId)
      .insert({
        kind: body.kind,
        full_name: body.full_name,
        email: body.email || "",
        phone: body.phone || "",
        company_name: body.company_name || "",
        notes: body.notes || "",
        created_by: ctx.userId,
      })
      .select("id, kind, full_name, email, phone, company_name")
      .single();

    if (error) {
      logError(error, { route: "POST /api/contacts" });
      return NextResponse.json({ error: "Failed to create contact" }, { status: 500 });
    }

    logger.info(
      { userId: ctx.userId, orgId: ctx.organizationId, contactId: data.id },
      "contact_created",
    );
    return NextResponse.json({ contact: data, organizationId: ctx.organizationId });
  } catch (err) {
    return denyResponse(err);
  }
}

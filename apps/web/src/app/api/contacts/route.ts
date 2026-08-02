import { NextResponse } from "next/server";
import { z } from "zod";
import { createClient } from "@/lib/supabase/server";
import { logError, logger } from "@/lib/logger";
import { assertPermission, getOrgContext, tenantFrom } from "@/lib/tenant";

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
    const supabase = await createClient();
    const ctx = await getOrgContext();
    if (!ctx) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    assertPermission(ctx, "contacts.read");

    const { data, error } = await tenantFrom(supabase, "contacts", ctx.organizationId)
      .select("id, kind, full_name, email, phone, company_name, notes, created_at")
      .order("created_at", { ascending: false })
      .limit(200);

    if (error) {
      logError(error, { route: "GET /api/contacts" });
      return NextResponse.json({ error: error.message }, { status: 500 });
    }
    return NextResponse.json({ organizationId: ctx.organizationId, contacts: data || [] });
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
    assertPermission(ctx, "contacts.write");

    const body = schema.parse(await request.json());
    const { data, error } = await tenantFrom(supabase, "contacts", ctx.organizationId)
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
      return NextResponse.json({ error: error.message }, { status: 500 });
    }

    logger.info(
      { userId: ctx.userId, orgId: ctx.organizationId, contactId: data.id },
      "contact_created",
    );
    return NextResponse.json({ contact: data, organizationId: ctx.organizationId });
  } catch (err) {
    logError(err, { route: "POST /api/contacts" });
    const status = (err as { status?: number }).status || 400;
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Bad request" },
      { status },
    );
  }
}

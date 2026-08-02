import { NextResponse } from "next/server";
import { z } from "zod";
import { createClient } from "@/lib/supabase/server";
import { logError, logger } from "@/lib/logger";
import { assertPermission, getOrgContext, tenantFrom } from "@/lib/tenant";

const schema = z.object({
  storage_path: z.string().min(1),
  file_name: z.string().min(1),
  content_type: z.string().optional(),
  byte_size: z.number().int().nonnegative().optional(),
  kind: z
    .enum(["document", "contract", "assignment", "title_packet", "other"])
    .default("document"),
  deal_id: z.string().uuid().optional(),
  lead_id: z.string().uuid().optional(),
  contact_id: z.string().uuid().optional(),
});

export async function GET() {
  try {
    const supabase = await createClient();
    const ctx = await getOrgContext();
    if (!ctx) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    assertPermission(ctx, "files.read");

    const { data, error } = await tenantFrom(supabase, "files", ctx.organizationId)
      .select(
        "id, file_name, content_type, byte_size, kind, storage_path, deal_id, lead_id, created_at",
      )
      .order("created_at", { ascending: false })
      .limit(200);

    if (error) {
      logError(error, { route: "GET /api/files" });
      return NextResponse.json({ error: error.message }, { status: 500 });
    }
    return NextResponse.json({ organizationId: ctx.organizationId, files: data || [] });
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
    assertPermission(ctx, "files.write");

    const body = schema.parse(await request.json());
    // Force storage paths under the org prefix to avoid cross-tenant object confusion.
    const storagePath = body.storage_path.startsWith(`${ctx.organizationId}/`)
      ? body.storage_path
      : `${ctx.organizationId}/${body.storage_path.replace(/^\/+/, "")}`;

    const { data, error } = await tenantFrom(supabase, "files", ctx.organizationId)
      .insert({
        storage_path: storagePath,
        file_name: body.file_name,
        content_type: body.content_type || "application/octet-stream",
        byte_size: body.byte_size ?? 0,
        kind: body.kind,
        deal_id: body.deal_id || null,
        lead_id: body.lead_id || null,
        contact_id: body.contact_id || null,
        created_by: ctx.userId,
      })
      .select("id, file_name, storage_path, kind")
      .single();

    if (error) {
      logError(error, { route: "POST /api/files" });
      return NextResponse.json({ error: error.message }, { status: 500 });
    }

    logger.info(
      { userId: ctx.userId, orgId: ctx.organizationId, fileId: data.id },
      "file_registered",
    );
    return NextResponse.json({ file: data, organizationId: ctx.organizationId });
  } catch (err) {
    logError(err, { route: "POST /api/files" });
    const status = (err as { status?: number }).status || 400;
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Bad request" },
      { status },
    );
  }
}

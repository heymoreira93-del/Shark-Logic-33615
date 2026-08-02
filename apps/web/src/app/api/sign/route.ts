import { NextResponse } from "next/server";
import { z } from "zod";
import { createServiceClient } from "@/lib/supabase/server";
import { logError, logger } from "@/lib/logger";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  try {
    const token = new URL(request.url).searchParams.get("token") || "";
    if (!token) return NextResponse.json({ error: "token required" }, { status: 400 });

    // Prefer Edge Function when available; fall back to service role.
    const base = process.env.NEXT_PUBLIC_SUPABASE_URL;
    const anon = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    if (base && anon) {
      const edge = await fetch(
        `${base}/functions/v1/sign-deal?token=${encodeURIComponent(token)}`,
        { headers: { Authorization: `Bearer ${anon}`, apikey: anon } },
      );
      if (edge.ok) {
        return NextResponse.json(await edge.json());
      }
    }

    const admin = createServiceClient();
    const { data, error } = await admin
      .from("deals")
      .select(
        "id, address, price, seller_name, buyer_name, status, deal_kind, assignment_fee, signed_at, signature",
      )
      .eq("sign_token", token)
      .maybeSingle();
    if (error) return NextResponse.json({ error: error.message }, { status: 500 });
    if (!data) return NextResponse.json({ error: "Deal not found" }, { status: 404 });
    return NextResponse.json({ deal: data });
  } catch (err) {
    logError(err, { route: "GET /api/sign" });
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Server error" },
      { status: 500 },
    );
  }
}

const postSchema = z.object({
  token: z.string().min(10),
  signature: z.string().min(2).max(200),
});

export async function POST(request: Request) {
  try {
    const body = postSchema.parse(await request.json());
    const base = process.env.NEXT_PUBLIC_SUPABASE_URL;
    const anon = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

    if (base && anon) {
      const edge = await fetch(`${base}/functions/v1/sign-deal`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${anon}`,
          apikey: anon,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      });
      const data = await edge.json();
      if (edge.ok) {
        logger.info({ tokenPrefix: body.token.slice(0, 6) }, "deal_signed_via_edge");
        return NextResponse.json(data);
      }
    }

    const admin = createServiceClient();
    const { data: deal, error } = await admin
      .from("deals")
      .select("id, status, organization_id")
      .eq("sign_token", body.token)
      .maybeSingle();
    if (error) return NextResponse.json({ error: error.message }, { status: 500 });
    if (!deal) return NextResponse.json({ error: "Deal not found" }, { status: 404 });
    if (deal.status === "SIGNED") return NextResponse.json({ ok: true, alreadySigned: true });

    const { error: updErr } = await admin
      .from("deals")
      .update({
        status: "SIGNED",
        signature: body.signature.trim(),
        signed_at: new Date().toISOString(),
      })
      .eq("id", deal.id);
    if (updErr) return NextResponse.json({ error: updErr.message }, { status: 500 });

    await admin.from("audit_logs").insert({
      organization_id: deal.organization_id,
      action: "deal.signed",
      entity_type: "deal",
      entity_id: deal.id,
      meta: { signature: body.signature.trim() },
    });

    logger.info({ dealId: deal.id }, "deal_signed");
    return NextResponse.json({ ok: true });
  } catch (err) {
    logError(err, { route: "POST /api/sign" });
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Bad request" },
      { status: 400 },
    );
  }
}

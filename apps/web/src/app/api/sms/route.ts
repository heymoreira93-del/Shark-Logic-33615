import { NextResponse } from "next/server";
import { z } from "zod";
import { createClient } from "@/lib/supabase/server";
import { logError, logger } from "@/lib/logger";
import { assertPermission, getOrgContext } from "@/lib/tenant";

const schema = z.object({
  to: z.string().regex(/^\+[1-9]\d{7,14}$/),
  body: z.string().min(3).max(1500),
  dealId: z.string().optional(),
});

export async function POST(request: Request) {
  try {
    const supabase = await createClient();
    const ctx = await getOrgContext();
    if (!ctx) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    assertPermission(ctx, "sms.send");

    const payload = schema.parse(await request.json());
    const functionsUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
    const anon = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    if (!functionsUrl || !anon) {
      return NextResponse.json({ error: "Supabase not configured" }, { status: 503 });
    }

    const {
      data: { session },
    } = await supabase.auth.getSession();
    if (!session?.access_token) {
      return NextResponse.json({ error: "No session" }, { status: 401 });
    }

    const res = await fetch(`${functionsUrl}/functions/v1/send-sms`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${session.access_token}`,
        apikey: anon,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) {
      logError(data, { route: "POST /api/sms", status: res.status });
      return NextResponse.json({ error: data.error || "SMS failed" }, { status: 502 });
    }

    logger.info(
      {
        userId: ctx.userId,
        orgId: ctx.organizationId,
        sid: data.sid,
        dealId: payload.dealId,
      },
      "sms_proxy_ok",
    );
    return NextResponse.json(data);
  } catch (err) {
    logError(err, { route: "POST /api/sms" });
    const status = (err as { status?: number }).status || 400;
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Bad request" },
      { status },
    );
  }
}

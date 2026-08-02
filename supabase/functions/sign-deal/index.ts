import { createClient } from "https://esm.sh/@supabase/supabase-js@2.49.1";
import { corsHeaders, jsonResponse } from "../_shared/cors.ts";
import { logError, logInfo } from "../_shared/log.ts";

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    const admin = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
    );

    if (req.method === "GET") {
      const url = new URL(req.url);
      const token = url.searchParams.get("token") || "";
      if (!token) return jsonResponse({ error: "token required" }, 400);
      const { data, error } = await admin
        .from("deals")
        .select(
          "id, address, price, seller_name, buyer_name, status, deal_kind, assignment_fee, signed_at, signature",
        )
        .eq("sign_token", token)
        .maybeSingle();
      if (error) return jsonResponse({ error: error.message }, 500);
      if (!data) return jsonResponse({ error: "Deal not found" }, 404);
      return jsonResponse({ deal: data });
    }

    if (req.method === "POST") {
      const { token, signature } = await req.json();
      const sig = String(signature || "").trim();
      if (!token || sig.length < 2) {
        return jsonResponse({ error: "token and signature required" }, 400);
      }

      const { data: deal, error: findErr } = await admin
        .from("deals")
        .select("id, status, organization_id")
        .eq("sign_token", token)
        .maybeSingle();
      if (findErr) return jsonResponse({ error: findErr.message }, 500);
      if (!deal) return jsonResponse({ error: "Deal not found" }, 404);
      if (deal.status === "SIGNED") {
        return jsonResponse({ ok: true, alreadySigned: true });
      }

      const { error: updErr } = await admin
        .from("deals")
        .update({
          status: "SIGNED",
          signature: sig,
          signed_at: new Date().toISOString(),
        })
        .eq("id", deal.id);
      if (updErr) return jsonResponse({ error: updErr.message }, 500);

      await admin.from("audit_logs").insert({
        organization_id: deal.organization_id,
        action: "deal.signed",
        entity_type: "deal",
        entity_id: deal.id,
        meta: { signature: sig },
      });

      // Optional operator SMS alert
      const notify = Deno.env.get("NOTIFY_PHONE")?.trim();
      const sid = Deno.env.get("TWILIO_ACCOUNT_SID")?.trim();
      const tokenTw = Deno.env.get("TWILIO_AUTH_TOKEN")?.trim();
      const from = Deno.env.get("TWILIO_PHONE_NUMBER")?.trim();
      if (notify && sid && tokenTw && from) {
        const form = new URLSearchParams({
          To: notify,
          From: from,
          Body: `DealShark: deal ${deal.id} SIGNED by ${sig}`,
        });
        await fetch(`https://api.twilio.com/2010-04-01/Accounts/${sid}/Messages.json`, {
          method: "POST",
          headers: {
            Authorization: "Basic " + btoa(`${sid}:${tokenTw}`),
            "Content-Type": "application/x-www-form-urlencoded",
          },
          body: form,
        });
      }

      logInfo("deal_signed", { dealId: deal.id });
      return jsonResponse({ ok: true });
    }

    return jsonResponse({ error: "Method not allowed" }, 405);
  } catch (err) {
    logError("sign_deal_exception", { err: String(err) });
    return jsonResponse({ error: String(err) }, 500);
  }
});

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.49.1";
import { corsHeaders, jsonResponse } from "../_shared/cors.ts";
import { logError, logInfo } from "../_shared/log.ts";

type Body = {
  to: string;
  body: string;
  dealId?: string;
};

function requiredEnv(name: string): string {
  const v = Deno.env.get(name)?.trim() || "";
  if (!v) throw new Error(`Missing secret ${name}`);
  return v;
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    const authHeader = req.headers.get("Authorization");
    if (!authHeader) return jsonResponse({ error: "Unauthorized" }, 401);

    const supabase = createClient(
      requiredEnv("SUPABASE_URL"),
      requiredEnv("SUPABASE_ANON_KEY"),
      { global: { headers: { Authorization: authHeader } } },
    );
    const {
      data: { user },
      error: userErr,
    } = await supabase.auth.getUser();
    if (userErr || !user) return jsonResponse({ error: "Unauthorized" }, 401);

    const payload = (await req.json()) as Body;
    const to = (payload.to || "").trim();
    const body = (payload.body || "").trim();
    if (!to.startsWith("+") || body.length < 3) {
      return jsonResponse({ error: "Invalid to/body" }, 400);
    }

    const sid = requiredEnv("TWILIO_ACCOUNT_SID");
    const token = requiredEnv("TWILIO_AUTH_TOKEN");
    const from = requiredEnv("TWILIO_PHONE_NUMBER");

    const twilioUrl = `https://api.twilio.com/2010-04-01/Accounts/${sid}/Messages.json`;
    const form = new URLSearchParams({ To: to, From: from, Body: body });
    const twilioRes = await fetch(twilioUrl, {
      method: "POST",
      headers: {
        Authorization: "Basic " + btoa(`${sid}:${token}`),
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: form,
    });
    const twilioJson = await twilioRes.json();
    if (!twilioRes.ok) {
      logError("twilio_send_failed", { status: twilioRes.status, twilioJson, userId: user.id });
      return jsonResponse({ error: "Twilio send failed", detail: twilioJson }, 502);
    }

    logInfo("sms_sent", { userId: user.id, to, sid: twilioJson.sid, dealId: payload.dealId });
    return jsonResponse({ ok: true, sid: twilioJson.sid });
  } catch (err) {
    logError("send_sms_exception", { err: String(err) });
    return jsonResponse({ error: String(err) }, 500);
  }
});

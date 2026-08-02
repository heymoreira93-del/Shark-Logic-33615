import { createClient } from "https://esm.sh/@supabase/supabase-js@2.49.1";
import { corsHeaders, jsonResponse } from "../_shared/cors.ts";
import { logError, logInfo } from "../_shared/log.ts";

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    const authHeader = req.headers.get("Authorization");
    if (!authHeader) return jsonResponse({ error: "Unauthorized" }, 401);

    const supabase = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_ANON_KEY")!,
      { global: { headers: { Authorization: authHeader } } },
    );
    const {
      data: { user },
    } = await supabase.auth.getUser();
    if (!user) return jsonResponse({ error: "Unauthorized" }, 401);

    const key = Deno.env.get("RENTCAST_API_KEY")?.trim();
    if (!key) return jsonResponse({ error: "RENTCAST_API_KEY not configured" }, 503);

    const { address } = await req.json();
    if (!address || typeof address !== "string") {
      return jsonResponse({ error: "address required" }, 400);
    }

    // Block phone-looking "addresses"
    if (/^\+?[\d\s().-]{7,}$/.test(address.trim())) {
      return jsonResponse({ error: "Property address looks like a phone number" }, 400);
    }

    const url = new URL("https://api.rentcast.io/v1/properties");
    url.searchParams.set("address", address.trim());

    const res = await fetch(url, { headers: { "X-Api-Key": key, Accept: "application/json" } });
    const data = await res.json();
    if (!res.ok) {
      logError("rentcast_failed", { status: res.status, userId: user.id });
      return jsonResponse({ error: "RentCast error", detail: data }, res.status);
    }

    logInfo("rentcast_ok", { userId: user.id, address });
    return jsonResponse({ ok: true, data });
  } catch (err) {
    logError("rentcast_exception", { err: String(err) });
    return jsonResponse({ error: String(err) }, 500);
  }
});

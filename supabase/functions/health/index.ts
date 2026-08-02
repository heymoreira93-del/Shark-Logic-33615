import { corsHeaders, jsonResponse } from "../_shared/cors.ts";
import { logInfo } from "../_shared/log.ts";

Deno.serve((req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }
  logInfo("healthcheck");
  return jsonResponse({
    ok: true,
    service: "dealshark-edge",
    time: new Date().toISOString(),
  });
});

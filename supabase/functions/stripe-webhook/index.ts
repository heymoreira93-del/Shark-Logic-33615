import { createClient } from "https://esm.sh/@supabase/supabase-js@2.49.1";
import Stripe from "https://esm.sh/stripe@14.25.0?target=deno";
import { corsHeaders, jsonResponse } from "../_shared/cors.ts";
import { logError, logInfo } from "../_shared/log.ts";

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  const stripeKey = Deno.env.get("STRIPE_SECRET_KEY");
  const webhookSecret = Deno.env.get("STRIPE_WEBHOOK_SECRET");
  if (!stripeKey || !webhookSecret) {
    return jsonResponse({ error: "Stripe secrets missing" }, 503);
  }

  const stripe = new Stripe(stripeKey, { apiVersion: "2023-10-16" });
  const signature = req.headers.get("stripe-signature");
  if (!signature) return jsonResponse({ error: "Missing stripe-signature" }, 400);

  try {
    const body = await req.text();
    const event = stripe.webhooks.constructEvent(body, signature, webhookSecret);

    if (event.type === "checkout.session.completed") {
      const session = event.data.object as Stripe.Checkout.Session;
      const dealId = session.metadata?.deal_id || session.client_reference_id;
      if (!dealId) {
        logError("stripe_missing_deal_id", { sessionId: session.id });
        return jsonResponse({ received: true, warning: "no deal_id" });
      }

      const admin = createClient(
        Deno.env.get("SUPABASE_URL")!,
        Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
      );
      const { error } = await admin
        .from("deals")
        .update({
          emd_paid: true,
          stripe_session_id: session.id,
          notes: "EMD paid via Stripe Checkout",
        })
        .eq("id", dealId);

      if (error) {
        logError("stripe_deal_update_failed", { dealId, error: error.message });
        return jsonResponse({ error: error.message }, 500);
      }
      logInfo("emd_marked_paid", { dealId, sessionId: session.id });
    }

    return jsonResponse({ received: true });
  } catch (err) {
    logError("stripe_webhook_exception", { err: String(err) });
    return jsonResponse({ error: String(err) }, 400);
  }
});

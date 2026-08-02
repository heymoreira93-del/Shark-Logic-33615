import { NextResponse } from "next/server";
import Stripe from "stripe";
import { createServiceClient } from "@/lib/supabase/server";
import { logError, logger } from "@/lib/logger";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  const secret = process.env.STRIPE_SECRET_KEY;
  const webhookSecret = process.env.STRIPE_WEBHOOK_SECRET;
  if (!secret || !webhookSecret) {
    return NextResponse.json({ error: "Stripe not configured" }, { status: 503 });
  }

  const stripe = new Stripe(secret);
  const signature = request.headers.get("stripe-signature");
  if (!signature) {
    return NextResponse.json({ error: "Missing stripe-signature" }, { status: 400 });
  }

  try {
    const body = await request.text();
    const event = stripe.webhooks.constructEvent(body, signature, webhookSecret);

    if (event.type === "checkout.session.completed") {
      const session = event.data.object as Stripe.Checkout.Session;
      const dealId = session.metadata?.deal_id || session.client_reference_id;
      if (!dealId) {
        logger.warn({ sessionId: session.id }, "stripe session missing deal_id");
        return NextResponse.json({ received: true });
      }

      const admin = createServiceClient();
      const { error } = await admin
        .from("deals")
        .update({
          emd_paid: true,
          stripe_session_id: session.id,
        })
        .eq("id", dealId);
      if (error) {
        logError(error, { dealId });
        return NextResponse.json({ error: error.message }, { status: 500 });
      }
      logger.info({ dealId, sessionId: session.id }, "emd_paid");
    }

    return NextResponse.json({ received: true });
  } catch (err) {
    logError(err, { route: "POST /api/webhooks/stripe" });
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Webhook error" },
      { status: 400 },
    );
  }
}

import { NextResponse } from "next/server";
import { logger } from "@/lib/logger";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
  const appUrl = process.env.NEXT_PUBLIC_APP_URL || process.env.APP_URL || "";
  const payload = {
    ok: true,
    service: "dealshark-web",
    time: new Date().toISOString(),
    env: {
      hasAppUrl: Boolean(appUrl),
      hasSupabaseUrl: Boolean(supabaseUrl),
      hasAnonKey: Boolean(process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY),
      hasServiceRole: Boolean(process.env.SUPABASE_SERVICE_ROLE_KEY),
      hasTwilio: Boolean(
        process.env.TWILIO_ACCOUNT_SID &&
          process.env.TWILIO_AUTH_TOKEN &&
          process.env.TWILIO_PHONE_NUMBER,
      ),
      hasStripe: Boolean(process.env.STRIPE_SECRET_KEY),
      hasRentcast: Boolean(process.env.RENTCAST_API_KEY),
      hasSentry: Boolean(process.env.SENTRY_DSN || process.env.NEXT_PUBLIC_SENTRY_DSN),
      productionAppUrlIsPublic: Boolean(appUrl) && !/localhost|127\.0\.0\.1/i.test(appUrl),
    },
  };
  logger.info(payload, "healthcheck");
  return NextResponse.json(payload);
}

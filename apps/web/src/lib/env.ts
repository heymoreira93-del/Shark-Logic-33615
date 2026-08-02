import { z } from "zod";

/**
 * Production env contract. No localhost defaults.
 * Secrets never ship in the client bundle — only NEXT_PUBLIC_* are public.
 */
const serverSchema = z.object({
  NODE_ENV: z.enum(["development", "test", "production"]).default("development"),
  APP_URL: z.string().url(),
  SUPABASE_SERVICE_ROLE_KEY: z.string().min(20).optional(),
  TWILIO_ACCOUNT_SID: z.string().optional(),
  TWILIO_AUTH_TOKEN: z.string().optional(),
  TWILIO_PHONE_NUMBER: z.string().optional(),
  STRIPE_SECRET_KEY: z.string().optional(),
  STRIPE_WEBHOOK_SECRET: z.string().optional(),
  STRIPE_EMD_DOLLARS: z.string().optional(),
  RENTCAST_API_KEY: z.string().optional(),
  SENTRY_DSN: z.string().optional(),
  LOG_LEVEL: z.string().default("info"),
});

const publicSchema = z.object({
  NEXT_PUBLIC_APP_URL: z.string().url(),
  NEXT_PUBLIC_SUPABASE_URL: z.string().url(),
  NEXT_PUBLIC_SUPABASE_ANON_KEY: z.string().min(20),
  NEXT_PUBLIC_SENTRY_DSN: z.string().optional(),
});

export type PublicEnv = z.infer<typeof publicSchema>;
export type ServerEnv = z.infer<typeof serverSchema>;

function isBuildPhase() {
  return process.env.NEXT_PHASE === "phase-production-build";
}

function requirePublicEnv(): PublicEnv {
  const parsed = publicSchema.safeParse({
    NEXT_PUBLIC_APP_URL: process.env.NEXT_PUBLIC_APP_URL,
    NEXT_PUBLIC_SUPABASE_URL: process.env.NEXT_PUBLIC_SUPABASE_URL,
    NEXT_PUBLIC_SUPABASE_ANON_KEY: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
    NEXT_PUBLIC_SENTRY_DSN: process.env.NEXT_PUBLIC_SENTRY_DSN,
  });

  if (parsed.success) return parsed.data;

  if (isBuildPhase()) {
    // Allow `next build` with placeholder public vars; runtime still validates.
    return {
      NEXT_PUBLIC_APP_URL: process.env.NEXT_PUBLIC_APP_URL || "https://build.invalid",
      NEXT_PUBLIC_SUPABASE_URL:
        process.env.NEXT_PUBLIC_SUPABASE_URL || "https://build.supabase.co",
      NEXT_PUBLIC_SUPABASE_ANON_KEY:
        process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "build-placeholder-anon-key-00000",
      NEXT_PUBLIC_SENTRY_DSN: process.env.NEXT_PUBLIC_SENTRY_DSN,
    };
  }

  throw new Error(
    `Missing public env: ${parsed.error.issues.map((i) => i.path.join(".")).join(", ")}. ` +
      "Set NEXT_PUBLIC_APP_URL, NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY in Vercel.",
  );
}

export function getPublicEnv(): PublicEnv {
  return requirePublicEnv();
}

export function getServerEnv(): ServerEnv {
  const publicEnv = requirePublicEnv();
  const parsed = serverSchema.safeParse({
    NODE_ENV: process.env.NODE_ENV,
    APP_URL: process.env.APP_URL || publicEnv.NEXT_PUBLIC_APP_URL,
    SUPABASE_SERVICE_ROLE_KEY: process.env.SUPABASE_SERVICE_ROLE_KEY,
    TWILIO_ACCOUNT_SID: process.env.TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN: process.env.TWILIO_AUTH_TOKEN,
    TWILIO_PHONE_NUMBER: process.env.TWILIO_PHONE_NUMBER,
    STRIPE_SECRET_KEY: process.env.STRIPE_SECRET_KEY,
    STRIPE_WEBHOOK_SECRET: process.env.STRIPE_WEBHOOK_SECRET,
    STRIPE_EMD_DOLLARS: process.env.STRIPE_EMD_DOLLARS,
    RENTCAST_API_KEY: process.env.RENTCAST_API_KEY,
    SENTRY_DSN: process.env.SENTRY_DSN || process.env.NEXT_PUBLIC_SENTRY_DSN,
    LOG_LEVEL: process.env.LOG_LEVEL || "info",
  });

  if (!parsed.success) {
    throw new Error(
      `Invalid server env: ${parsed.error.issues.map((i) => i.path.join(".")).join(", ")}`,
    );
  }

  if (
    parsed.data.NODE_ENV === "production" &&
    /localhost|127\.0\.0\.1/i.test(parsed.data.APP_URL)
  ) {
    throw new Error("APP_URL cannot be localhost in production");
  }

  return parsed.data;
}

export function assertNoLocalhostUrl(url: string, label: string) {
  if (/localhost|127\.0\.0\.1|0\.0\.0\.0|\.local\b/i.test(url)) {
    throw new Error(`${label} must be a public HTTPS URL in SaaS mode (got ${url})`);
  }
}

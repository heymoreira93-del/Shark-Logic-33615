import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { logger } from "@/lib/logger";
import { getOrgContext, requireOrgContext } from "@/lib/tenant";

/** @deprecated Prefer requireOrgContext() for multi-tenant routes. */
export async function requireUser() {
  const supabase = await createClient();
  const {
    data: { user },
    error,
  } = await supabase.auth.getUser();

  if (error) {
    logger.warn({ err: error.message }, "auth.getUser failed");
  }
  if (!user) {
    redirect("/login");
  }
  return { supabase, user };
}

export async function getSessionUser() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  return { supabase, user };
}

export { getOrgContext, requireOrgContext };

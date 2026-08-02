import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { logger } from "@/lib/logger";

export async function POST(request: Request) {
  const supabase = await createClient();
  const { error } = await supabase.auth.signOut();
  if (error) logger.warn({ err: error.message }, "signout error");
  return NextResponse.redirect(new URL("/login", request.url), { status: 303 });
}

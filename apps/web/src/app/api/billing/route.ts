import { NextResponse } from "next/server";
import { denyResponse, requireApiAuth } from "@/lib/authz";

/** Billing summary — Owner only (billing.manage). Never returns data without permission. */
export async function GET() {
  try {
    const ctx = await requireApiAuth("billing.manage");
    return NextResponse.json({
      organizationId: ctx.organizationId,
      organization: ctx.organization.name,
      plan: "production",
      status: "active",
      note: "Connect Stripe Billing / customer portal in a follow-up.",
    });
  } catch (err) {
    return denyResponse(err);
  }
}

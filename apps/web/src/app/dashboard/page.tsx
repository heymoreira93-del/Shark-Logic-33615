import Link from "next/link";
import { requirePageAuth } from "@/lib/authz";
import { tenantFrom } from "@/lib/tenant";
import { PERMISSION_LABELS } from "@/lib/authz/permissions";

export default async function DashboardPage() {
  const ctx = await requirePageAuth(["leads.view", "deals.view"], { anyOf: true });
  const { supabase, organizationId, email, permissions } = ctx;

  const canLeads = permissions.includes("leads.view");
  const canDeals = permissions.includes("deals.view");

  const [{ count: leadCount }, { count: dealCount }] = await Promise.all([
    canLeads
      ? tenantFrom(supabase, "leads", organizationId).select("*", {
          count: "exact",
          head: true,
        })
      : Promise.resolve({ count: null }),
    canDeals
      ? tenantFrom(supabase, "deals", organizationId).select("*", {
          count: "exact",
          head: true,
        })
      : Promise.resolve({ count: null }),
  ]);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-semibold text-teal-950">Command Center</h1>
        <p className="mt-1 text-teal-900/70">
          {email} · {ctx.membership.roles?.name || "Member"}
        </p>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        {canLeads ? (
          <Link
            href="/dashboard/leads"
            className="card-panel rounded-2xl p-5 transition hover:border-teal-700/30"
          >
            <p className="text-sm text-teal-900/60">Leads</p>
            <p className="mt-2 text-3xl font-semibold">{leadCount ?? 0}</p>
          </Link>
        ) : null}
        {canDeals ? (
          <Link
            href="/dashboard/deals"
            className="card-panel rounded-2xl p-5 transition hover:border-teal-700/30"
          >
            <p className="text-sm text-teal-900/60">Deals</p>
            <p className="mt-2 text-3xl font-semibold">{dealCount ?? 0}</p>
          </Link>
        ) : null}
      </div>
      <div className="card-panel rounded-2xl p-6">
        <h2 className="text-lg font-semibold">Your permissions</h2>
        <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-teal-900/80">
          {permissions.map((key) => (
            <li key={key}>{PERMISSION_LABELS[key]}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}

import Link from "next/link";
import { requireOrgContext, tenantFrom } from "@/lib/tenant";

export default async function DashboardPage() {
  const ctx = await requireOrgContext();
  const { supabase, organizationId, email, permissions } = ctx;

  const [{ count: leadCount }, { count: dealCount }, { count: contactCount }, { count: fileCount }] =
    await Promise.all([
      tenantFrom(supabase, "leads", organizationId).select("*", { count: "exact", head: true }),
      tenantFrom(supabase, "deals", organizationId).select("*", { count: "exact", head: true }),
      tenantFrom(supabase, "contacts", organizationId).select("*", {
        count: "exact",
        head: true,
      }),
      tenantFrom(supabase, "files", organizationId).select("*", { count: "exact", head: true }),
    ]);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-semibold text-teal-950">Command Center</h1>
        <p className="mt-1 text-teal-900/70">
          {email} · org <code className="text-xs">{organizationId}</code>
        </p>
      </div>
      <div className="grid gap-4 md:grid-cols-4">
        {[
          { label: "Leads", value: leadCount ?? 0, href: "/dashboard/leads" },
          { label: "Deals", value: dealCount ?? 0, href: "/dashboard/deals" },
          { label: "Contacts", value: contactCount ?? 0, href: "/dashboard/contacts" },
          { label: "Files", value: fileCount ?? 0, href: "/dashboard/files" },
        ].map((card) => (
          <Link
            key={card.label}
            href={card.href}
            className="card-panel rounded-2xl p-5 transition hover:border-teal-700/30"
          >
            <p className="text-sm text-teal-900/60">{card.label}</p>
            <p className="mt-2 text-3xl font-semibold">{card.value}</p>
          </Link>
        ))}
      </div>
      <div className="card-panel rounded-2xl p-6">
        <h2 className="text-lg font-semibold">Your permissions</h2>
        <p className="mt-2 text-sm text-teal-900/70">
          {permissions.length ? permissions.join(", ") : "No permissions loaded"}
        </p>
      </div>
    </div>
  );
}

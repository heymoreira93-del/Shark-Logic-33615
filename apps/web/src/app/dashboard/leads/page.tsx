import { requireOrgContext, tenantFrom } from "@/lib/tenant";

export default async function LeadsPage() {
  const ctx = await requireOrgContext();
  const { data: leads, error } = await tenantFrom(ctx.supabase, "leads", ctx.organizationId)
    .select("id, address, seller_name, seller_phone, arv, mao, status, created_at")
    .order("created_at", { ascending: false })
    .limit(100);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Leads</h1>
      <p className="text-sm text-teal-900/60">Scoped to {ctx.organization.name}</p>
      {error ? <p className="text-red-700">{error.message}</p> : null}
      <div className="card-panel overflow-x-auto rounded-2xl">
        <table className="min-w-full text-left text-sm">
          <thead className="border-b border-teal-900/10 text-teal-900/60">
            <tr>
              <th className="px-4 py-3">Address</th>
              <th className="px-4 py-3">Seller</th>
              <th className="px-4 py-3">Phone</th>
              <th className="px-4 py-3">MAO</th>
              <th className="px-4 py-3">Status</th>
            </tr>
          </thead>
          <tbody>
            {((leads || []) as Array<{
              id: string;
              address: string;
              seller_name: string | null;
              seller_phone: string | null;
              mao: number | null;
              status: string;
            }>).map((lead) => (
              <tr key={lead.id} className="border-b border-teal-900/5">
                <td className="px-4 py-3">{lead.address}</td>
                <td className="px-4 py-3">{lead.seller_name || "—"}</td>
                <td className="px-4 py-3">{lead.seller_phone || "—"}</td>
                <td className="px-4 py-3">${Number(lead.mao || 0).toLocaleString()}</td>
                <td className="px-4 py-3">{lead.status}</td>
              </tr>
            ))}
            {!leads?.length ? (
              <tr>
                <td className="px-4 py-6 text-teal-900/60" colSpan={5}>
                  No leads yet — save one from Calculator.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}

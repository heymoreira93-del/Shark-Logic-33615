import { requirePageAuth } from "@/lib/authz";
import { tenantFrom } from "@/lib/tenant";

export default async function MembersPage() {
  const ctx = await requirePageAuth("users.manage");

  const { data: members, error } = await tenantFrom(
    ctx.supabase,
    "organization_members",
    ctx.organizationId,
  )
    .select("id, user_id, status, created_at, role_id")
    .order("created_at", { ascending: true });

  const typedMembers = (members || []) as Array<{
    id: string;
    user_id: string;
    status: string;
    created_at: string;
    role_id: string;
  }>;

  const roleIds = [...new Set(typedMembers.map((m) => m.role_id))];
  const { data: roles } = roleIds.length
    ? await ctx.supabase.from("roles").select("id, key, name").in("id", roleIds)
    : { data: [] as Array<{ id: string; key: string; name: string }> };
  const roleMap = new Map((roles || []).map((r) => [r.id, r]));

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Manage users</h1>
      <p className="text-sm text-teal-900/60">Members of {ctx.organization.name}</p>
      {error ? <p className="text-red-700">Unable to load members</p> : null}
      <div className="card-panel overflow-x-auto rounded-2xl">
        <table className="min-w-full text-left text-sm">
          <thead className="border-b border-teal-900/10 text-teal-900/60">
            <tr>
              <th className="px-4 py-3">User ID</th>
              <th className="px-4 py-3">Role</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Joined</th>
            </tr>
          </thead>
          <tbody>
            {typedMembers.map((member) => {
              const role = roleMap.get(member.role_id);
              return (
                <tr key={member.id} className="border-b border-teal-900/5">
                  <td className="px-4 py-3 font-mono text-xs">{member.user_id}</td>
                  <td className="px-4 py-3">{role?.name || role?.key || "—"}</td>
                  <td className="px-4 py-3">{member.status}</td>
                  <td className="px-4 py-3">
                    {member.created_at
                      ? new Date(member.created_at).toLocaleDateString()
                      : "—"}
                  </td>
                </tr>
              );
            })}
            {!typedMembers.length ? (
              <tr>
                <td className="px-4 py-6 text-teal-900/60" colSpan={4}>
                  No members found.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}

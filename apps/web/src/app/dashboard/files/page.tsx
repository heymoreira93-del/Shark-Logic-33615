import { requirePageAuth } from "@/lib/authz";
import { tenantFrom } from "@/lib/tenant";

export default async function FilesPage() {
  const ctx = await requirePageAuth("deals.view");
  const { data: files, error } = await tenantFrom(ctx.supabase, "files", ctx.organizationId)
    .select("id, file_name, kind, content_type, byte_size, storage_path, created_at")
    .order("created_at", { ascending: false })
    .limit(200);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Files</h1>
      <p className="text-sm text-teal-900/60">Scoped to {ctx.organization.name}</p>
      {error ? <p className="text-red-700">Unable to load files</p> : null}
      <div className="card-panel overflow-x-auto rounded-2xl">
        <table className="min-w-full text-left text-sm">
          <thead className="border-b border-teal-900/10 text-teal-900/60">
            <tr>
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Kind</th>
              <th className="px-4 py-3">Size</th>
              <th className="px-4 py-3">Path</th>
            </tr>
          </thead>
          <tbody>
            {((files || []) as Array<{
              id: string;
              file_name: string;
              kind: string;
              byte_size: number;
              storage_path: string;
            }>).map((file) => (
              <tr key={file.id} className="border-b border-teal-900/5">
                <td className="px-4 py-3">{file.file_name}</td>
                <td className="px-4 py-3">{file.kind}</td>
                <td className="px-4 py-3">{Number(file.byte_size || 0).toLocaleString()} B</td>
                <td className="px-4 py-3 font-mono text-xs">{file.storage_path}</td>
              </tr>
            ))}
            {!files?.length ? (
              <tr>
                <td className="px-4 py-6 text-teal-900/60" colSpan={4}>
                  No files registered for this organization yet.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}

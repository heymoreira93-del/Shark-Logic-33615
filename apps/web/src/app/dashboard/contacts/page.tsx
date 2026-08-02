import { ContactsClient } from "./contacts-client";
import { requireOrgContext, tenantFrom } from "@/lib/tenant";

export default async function ContactsPage() {
  const ctx = await requireOrgContext();
  const { data: contacts, error } = await tenantFrom(
    ctx.supabase,
    "contacts",
    ctx.organizationId,
  )
    .select("id, kind, full_name, email, phone, company_name, created_at")
    .order("created_at", { ascending: false })
    .limit(200);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Contacts</h1>
      <p className="text-sm text-teal-900/60">Scoped to {ctx.organization.name}</p>
      {error ? <p className="text-red-700">{error.message}</p> : null}
      <ContactsClient
        initialContacts={(contacts || []) as Array<{
          id: string;
          kind: string;
          full_name: string;
          email: string | null;
          phone: string | null;
          company_name: string | null;
          created_at: string;
        }>}
      />
    </div>
  );
}

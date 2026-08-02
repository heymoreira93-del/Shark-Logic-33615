import { requirePageAuth } from "@/lib/authz";

export default async function BillingPage() {
  const ctx = await requirePageAuth("billing.manage");

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Billing</h1>
      <p className="text-sm text-teal-900/60">{ctx.organization.name}</p>
      <div className="card-panel max-w-xl rounded-2xl p-6">
        <p className="text-sm text-teal-900/80">
          Owner-only billing workspace. Stripe customer portal / invoices can be wired to this
          page next.
        </p>
        <dl className="mt-4 space-y-2 text-sm">
          <div className="flex justify-between">
            <dt>Plan</dt>
            <dd className="font-medium">Production</dd>
          </div>
          <div className="flex justify-between">
            <dt>Status</dt>
            <dd className="font-medium">Active</dd>
          </div>
        </dl>
      </div>
    </div>
  );
}

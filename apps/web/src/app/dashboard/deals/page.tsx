import { DealsClient } from "./deals-client";
import { getPublicEnv } from "@/lib/env";
import { requirePageAuth } from "@/lib/authz";
import { tenantFrom } from "@/lib/tenant";

export default async function DealsPage() {
  const ctx = await requirePageAuth("deals.view");
  const canEdit = ctx.permissions.includes("deals.edit");
  const { data: deals, error } = await tenantFrom(ctx.supabase, "deals", ctx.organizationId)
    .select(
      "id, address, seller_name, buyer_name, price, status, deal_kind, sign_token, emd_paid, created_at",
    )
    .order("created_at", { ascending: false })
    .limit(100);

  const appUrl = getPublicEnv().NEXT_PUBLIC_APP_URL;

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Deals</h1>
      <p className="text-sm text-teal-900/60">Scoped to {ctx.organization.name}</p>
      {error ? <p className="text-red-700">Unable to load deals</p> : null}
      <DealsClient
        initialDeals={
          canEdit
            ? ((deals || []) as Array<{
                id: string;
                address: string;
                seller_name: string | null;
                buyer_name: string | null;
                price: number | null;
                status: string;
                deal_kind: string;
                sign_token: string;
                emd_paid: boolean;
                created_at: string;
              }>)
            : ((deals || []) as Array<{
                id: string;
                address: string;
                seller_name: string | null;
                buyer_name: string | null;
                price: number | null;
                status: string;
                deal_kind: string;
                sign_token: string;
                emd_paid: boolean;
                created_at: string;
              }>)
        }
        appUrl={appUrl}
        canEdit={canEdit}
      />
    </div>
  );
}

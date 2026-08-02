import { SettingsClient } from "./settings-client";
import { requirePageAuth } from "@/lib/authz";
import { tenantFrom } from "@/lib/tenant";

export default async function SettingsPage() {
  const ctx = await requirePageAuth("settings.manage");
  const { data: settings, error } = await tenantFrom(
    ctx.supabase,
    "organization_settings",
    ctx.organizationId,
  )
    .select("*")
    .maybeSingle();

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Organization settings</h1>
      <p className="text-sm text-teal-900/60">{ctx.organization.name}</p>
      {error ? <p className="text-red-700">Unable to load settings</p> : null}
      <SettingsClient
        initialSettings={
          (settings as {
            assignor_name: string;
            default_assignment_fee: number;
            default_emd: number;
            notify_phone: string;
            timezone: string;
          } | null) || {
            assignor_name: "DealShark Acquisitions",
            default_assignment_fee: 10000,
            default_emd: 2500,
            notify_phone: "",
            timezone: "America/New_York",
          }
        }
        canWrite
      />
    </div>
  );
}

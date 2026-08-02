import Link from "next/link";
import { requireOrgContext } from "@/lib/tenant";

export default async function UnauthorizedPage() {
  const ctx = await requireOrgContext();
  return (
    <div className="card-panel mx-auto max-w-lg rounded-2xl p-8 text-center">
      <h1 className="text-2xl font-semibold text-teal-950">Access denied</h1>
      <p className="mt-3 text-teal-900/70">
        Your role ({ctx.membership.roles?.name || "member"}) does not have permission for that
        page. No data was returned.
      </p>
      <Link href="/dashboard" className="btn-primary mt-6 inline-block">
        Back to dashboard
      </Link>
    </div>
  );
}

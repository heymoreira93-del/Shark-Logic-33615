import Link from "next/link";
import { requireOrgContext } from "@/lib/tenant";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const ctx = await requireOrgContext();
  const roleKey = ctx.membership.roles?.key || "member";

  return (
    <div className="min-h-screen">
      <header className="border-b border-teal-900/10 bg-white/60 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-6 py-4">
          <div>
            <p className="text-xs font-semibold tracking-[0.18em] text-teal-800 uppercase">
              DealShark
            </p>
            <p className="text-sm text-teal-900/70">
              {ctx.organization.name} · {roleKey}
            </p>
          </div>
          <nav className="flex flex-wrap gap-3 text-sm font-medium">
            <Link href="/dashboard">Overview</Link>
            <Link href="/dashboard/calculator">Calculator</Link>
            <Link href="/dashboard/leads">Leads</Link>
            <Link href="/dashboard/deals">Deals</Link>
            <Link href="/dashboard/contacts">Contacts</Link>
            <Link href="/dashboard/files">Files</Link>
            <Link href="/dashboard/settings">Settings</Link>
            <Link href="/dashboard/members">Members</Link>
            <form action="/auth/signout" method="post">
              <button type="submit" className="text-teal-900/60">
                Sign out
              </button>
            </form>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
    </div>
  );
}

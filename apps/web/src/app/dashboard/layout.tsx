import Link from "next/link";
import { requireOrgContext } from "@/lib/tenant";
import { hasPermission, type PermissionKey } from "@/lib/authz";

const NAV: Array<{ href: string; label: string; permission?: PermissionKey }> = [
  { href: "/dashboard", label: "Overview" },
  { href: "/dashboard/calculator", label: "Calculator", permission: "leads.edit" },
  { href: "/dashboard/leads", label: "Leads", permission: "leads.view" },
  { href: "/dashboard/deals", label: "Deals", permission: "deals.view" },
  { href: "/dashboard/contacts", label: "Contacts", permission: "leads.view" },
  { href: "/dashboard/files", label: "Files", permission: "deals.view" },
  { href: "/dashboard/members", label: "Users", permission: "users.manage" },
  { href: "/dashboard/billing", label: "Billing", permission: "billing.manage" },
  { href: "/dashboard/settings", label: "Settings", permission: "settings.manage" },
];

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const ctx = await requireOrgContext();
  const roleKey = ctx.membership.roles?.key || "member";
  const links = NAV.filter(
    (item) => !item.permission || hasPermission(ctx.permissions, item.permission),
  );

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
            {links.map((item) => (
              <Link key={item.href} href={item.href}>
                {item.label}
              </Link>
            ))}
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

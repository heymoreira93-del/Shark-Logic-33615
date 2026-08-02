import Link from "next/link";
import { getSessionUser } from "@/lib/auth";
import { redirect } from "next/navigation";

export default async function HomePage() {
  const { user } = await getSessionUser();
  if (user) redirect("/dashboard");

  return (
    <main className="mx-auto flex min-h-screen max-w-5xl flex-col justify-center px-6 py-16">
      <p className="text-sm font-semibold tracking-[0.2em] text-teal-800 uppercase">DealShark</p>
      <h1 className="mt-4 max-w-2xl text-5xl font-semibold tracking-tight text-teal-950 md:text-6xl">
        Get properties under contract. Assign. Collect the fee.
      </h1>
      <p className="mt-5 max-w-xl text-lg text-teal-900/80">
        Production SaaS for wholesalers — auth, deals, secure e-sign links, SMS, and Stripe EMD
        backed by Supabase.
      </p>
      <div className="mt-8 flex flex-wrap gap-3">
        <Link href="/signup" className="btn-primary">
          Start free workspace
        </Link>
        <Link
          href="/login"
          className="rounded-lg border border-teal-900/20 bg-white/70 px-4 py-2.5 font-semibold"
        >
          Log in
        </Link>
      </div>
    </main>
  );
}

"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { createClient } from "@/lib/supabase/client";

export default function SignupPage() {
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    setInfo("");
    const supabase = createClient();
    const origin = process.env.NEXT_PUBLIC_APP_URL;
    if (!origin) {
      setError("NEXT_PUBLIC_APP_URL is not configured");
      setLoading(false);
      return;
    }
    const { data, error: err } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: { full_name: fullName },
        emailRedirectTo: `${origin}/auth/callback`,
      },
    });
    setLoading(false);
    if (err) {
      setError(err.message);
      return;
    }
    if (data.session) {
      router.replace("/dashboard");
      router.refresh();
      return;
    }
    setInfo("Check your email to confirm your account, then log in.");
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6">
      <h1 className="text-3xl font-semibold text-teal-950">Create your workspace</h1>
      <form onSubmit={onSubmit} className="card-panel mt-6 space-y-4 rounded-2xl p-6">
        <label className="block text-sm font-medium">
          Full name
          <input
            className="input mt-1"
            required
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
          />
        </label>
        <label className="block text-sm font-medium">
          Work email
          <input
            className="input mt-1"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>
        <label className="block text-sm font-medium">
          Password
          <input
            className="input mt-1"
            type="password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        {error ? <p className="text-sm text-red-700">{error}</p> : null}
        {info ? <p className="text-sm text-teal-800">{info}</p> : null}
        <button className="btn-primary w-full" disabled={loading} type="submit">
          {loading ? "Creating…" : "Create workspace"}
        </button>
      </form>
      <p className="mt-4 text-sm text-teal-900/70">
        Already have an account? <Link href="/login">Log in</Link>
      </p>
    </main>
  );
}

"use client";

import { FormEvent, useEffect, useState } from "react";
import { useParams } from "next/navigation";

type Deal = {
  id: string;
  address: string;
  price: number;
  seller_name: string;
  buyer_name: string;
  status: string;
  deal_kind: string;
  assignment_fee: number;
  signature: string;
  signed_at: string | null;
};

export default function SignPage() {
  const params = useParams<{ token: string }>();
  const token = params.token;
  const [deal, setDeal] = useState<Deal | null>(null);
  const [error, setError] = useState("");
  const [signature, setSignature] = useState("");
  const [done, setDone] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      setLoading(true);
      const res = await fetch(`/api/sign?token=${encodeURIComponent(token)}`);
      const data = await res.json();
      setLoading(false);
      if (!res.ok) {
        setError(data.error || "Unable to load agreement");
        return;
      }
      setDeal(data.deal);
      if (data.deal.status === "SIGNED") setDone(true);
    }
    load();
  }, [token]);

  async function onSign(e: FormEvent) {
    e.preventDefault();
    const res = await fetch("/api/sign", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token, signature }),
    });
    const data = await res.json();
    if (!res.ok) {
      setError(data.error || "Sign failed");
      return;
    }
    setDone(true);
  }

  if (loading) {
    return <main className="mx-auto max-w-lg px-6 py-16">Loading agreement…</main>;
  }

  if (error && !deal) {
    return (
      <main className="mx-auto max-w-lg px-6 py-16">
        <p className="text-red-700">{error}</p>
      </main>
    );
  }

  const isAssignment = deal?.deal_kind === "assignment";

  return (
    <main className="mx-auto max-w-lg px-6 py-16">
      <p className="text-xs font-semibold tracking-[0.18em] text-teal-800 uppercase">DealShark</p>
      <h1 className="mt-3 text-3xl font-semibold text-teal-950">
        {isAssignment ? "Assignment agreement" : "Purchase agreement"}
      </h1>
      <div className="card-panel mt-6 space-y-2 rounded-2xl p-6 text-sm">
        <p>
          <span className="text-teal-900/60">Property:</span> {deal?.address}
        </p>
        <p>
          <span className="text-teal-900/60">Price:</span> $
          {Number(deal?.price || 0).toLocaleString()}
        </p>
        <p>
          <span className="text-teal-900/60">
            {isAssignment ? "Assignee" : "Seller"}:
          </span>{" "}
          {isAssignment ? deal?.buyer_name : deal?.seller_name}
        </p>
        <p>
          <span className="text-teal-900/60">Status:</span> {deal?.status}
        </p>
      </div>

      {done ? (
        <p className="mt-6 rounded-xl bg-teal-900 px-4 py-3 font-medium text-white">
          Signed. Thank you — the wholesaler has been notified.
        </p>
      ) : (
        <form onSubmit={onSign} className="card-panel mt-6 space-y-4 rounded-2xl p-6">
          <label className="block text-sm font-medium">
            Type your legal name to sign
            <input
              className="input mt-1"
              required
              minLength={2}
              value={signature}
              onChange={(e) => setSignature(e.target.value)}
            />
          </label>
          {error ? <p className="text-sm text-red-700">{error}</p> : null}
          <button className="btn-primary w-full" type="submit">
            Sign agreement
          </button>
        </form>
      )}
    </main>
  );
}

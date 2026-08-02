"use client";

import { FormEvent, useState } from "react";

type Deal = {
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
};

export function DealsClient({
  initialDeals,
  appUrl,
  canEdit = false,
}: {
  initialDeals: Deal[];
  appUrl: string;
  canEdit?: boolean;
}) {
  const [deals, setDeals] = useState(initialDeals);
  const [address, setAddress] = useState("");
  const [sellerName, setSellerName] = useState("");
  const [sellerPhone, setSellerPhone] = useState("");
  const [price, setPrice] = useState(0);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  async function createDeal(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMsg("");
    const res = await fetch("/api/deals", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        address,
        seller_name: sellerName,
        seller_phone: sellerPhone,
        price,
        deal_kind: "purchase",
      }),
    });
    const data = await res.json();
    setBusy(false);
    if (!res.ok) {
      setMsg(data.error || "Failed");
      return;
    }
    setDeals((prev) => [data.deal, ...prev]);
    setMsg(`Deal created. Sign link: ${appUrl}/sign/${data.deal.sign_token}`);
    setAddress("");
    setSellerName("");
    setSellerPhone("");
  }

  async function sendSms(deal: Deal) {
    if (!deal.seller_name && !sellerPhone) {
      setMsg("Add seller phone on the deal first.");
      return;
    }
    const phone = prompt("Seller phone E.164 (+1…)", "");
    if (!phone) return;
    const body = `Hi, your agreement for ${deal.address} is ready. Sign here: ${appUrl}/sign/${deal.sign_token}`;
    const res = await fetch("/api/sms", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ to: phone, body, dealId: deal.id }),
    });
    const data = await res.json();
    setMsg(res.ok ? `SMS sent (${data.sid})` : data.error || "SMS failed");
  }

  return (
    <div className="space-y-6">
      {canEdit ? (
      <form onSubmit={createDeal} className="card-panel grid gap-3 rounded-2xl p-5 md:grid-cols-2">
        <label className="text-sm font-medium md:col-span-2">
          Address
          <input
            className="input mt-1"
            required
            value={address}
            onChange={(e) => setAddress(e.target.value)}
          />
        </label>
        <label className="text-sm font-medium">
          Seller name
          <input
            className="input mt-1"
            required
            value={sellerName}
            onChange={(e) => setSellerName(e.target.value)}
          />
        </label>
        <label className="text-sm font-medium">
          Seller phone
          <input
            className="input mt-1"
            value={sellerPhone}
            onChange={(e) => setSellerPhone(e.target.value)}
            placeholder="+18135551212"
          />
        </label>
        <label className="text-sm font-medium">
          Offer price
          <input
            className="input mt-1"
            type="number"
            value={price}
            onChange={(e) => setPrice(Number(e.target.value))}
          />
        </label>
        <div className="flex items-end">
          <button className="btn-primary" disabled={busy} type="submit">
            Create deal + e-sign link
          </button>
        </div>
      </form>
      ) : (
        <p className="text-sm text-teal-900/60">View-only — your role cannot create deals.</p>
      )}
      {msg ? <p className="text-sm text-teal-800">{msg}</p> : null}
      <div className="card-panel overflow-x-auto rounded-2xl">
        <table className="min-w-full text-left text-sm">
          <thead className="border-b border-teal-900/10 text-teal-900/60">
            <tr>
              <th className="px-4 py-3">Address</th>
              <th className="px-4 py-3">Seller</th>
              <th className="px-4 py-3">Price</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">EMD</th>
              <th className="px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {deals.map((deal) => (
              <tr key={deal.id} className="border-b border-teal-900/5">
                <td className="px-4 py-3">{deal.address}</td>
                <td className="px-4 py-3">{deal.seller_name || "—"}</td>
                <td className="px-4 py-3">${Number(deal.price || 0).toLocaleString()}</td>
                <td className="px-4 py-3">{deal.status}</td>
                <td className="px-4 py-3">{deal.emd_paid ? "PAID" : "—"}</td>
                <td className="space-x-2 px-4 py-3">
                  <a
                    className="underline"
                    href={`/sign/${deal.sign_token}`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Open sign
                  </a>
                  {canEdit ? (
                    <button type="button" className="underline" onClick={() => sendSms(deal)}>
                      SMS
                    </button>
                  ) : null}
                </td>
              </tr>
            ))}
            {!deals.length ? (
              <tr>
                <td className="px-4 py-6 text-teal-900/60" colSpan={6}>
                  No deals yet.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}

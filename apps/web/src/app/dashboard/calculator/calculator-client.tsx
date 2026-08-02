"use client";

import { FormEvent, useMemo, useState } from "react";
import { calculateMao } from "@/lib/mao";

export function CalculatorClient({ canEdit }: { canEdit: boolean }) {
  const [address, setAddress] = useState("");
  const [arv, setArv] = useState(300000);
  const [sqft, setSqft] = useState(1500);
  const [fee, setFee] = useState(10000);
  const [rehabLevel, setRehabLevel] = useState<"light" | "medium" | "heavy">("medium");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  const result = useMemo(
    () => calculateMao({ arv, sqft, fee, rehabLevel }),
    [arv, sqft, fee, rehabLevel],
  );

  async function saveLead(e: FormEvent) {
    e.preventDefault();
    if (!canEdit) return;
    setBusy(true);
    setMsg("");
    const res = await fetch("/api/leads", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        address,
        arv: result.arv,
        mao: result.offerPrice,
        wholesale_fee: fee,
        zip_code: "",
        status: "New Lead",
      }),
    });
    const data = await res.json();
    setBusy(false);
    if (!res.ok) {
      setMsg(data.error || "Failed to save lead");
      return;
    }
    setMsg(`Lead saved (${data.id}).`);
  }

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <form onSubmit={saveLead} className="card-panel space-y-4 rounded-2xl p-6">
        <h1 className="text-2xl font-semibold">MAO Calculator</h1>
        {!canEdit ? (
          <p className="text-sm text-red-700">Edit Leads permission required to save.</p>
        ) : null}
        <label className="block text-sm font-medium">
          Property address
          <input
            className="input mt-1"
            required
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            placeholder="8310 Regina Pl, Tampa, FL"
          />
        </label>
        <div className="grid grid-cols-2 gap-3">
          <label className="block text-sm font-medium">
            ARV
            <input
              className="input mt-1"
              type="number"
              value={arv}
              onChange={(e) => setArv(Number(e.target.value))}
            />
          </label>
          <label className="block text-sm font-medium">
            Sqft
            <input
              className="input mt-1"
              type="number"
              value={sqft}
              onChange={(e) => setSqft(Number(e.target.value))}
            />
          </label>
          <label className="block text-sm font-medium">
            Fee
            <input
              className="input mt-1"
              type="number"
              value={fee}
              onChange={(e) => setFee(Number(e.target.value))}
            />
          </label>
          <label className="block text-sm font-medium">
            Rehab
            <select
              className="input mt-1"
              value={rehabLevel}
              onChange={(e) => setRehabLevel(e.target.value as typeof rehabLevel)}
            >
              <option value="light">Light</option>
              <option value="medium">Medium</option>
              <option value="heavy">Heavy</option>
            </select>
          </label>
        </div>
        <button className="btn-primary" disabled={busy || !canEdit} type="submit">
          {busy ? "Saving…" : "Save lead to workspace"}
        </button>
        {msg ? <p className="text-sm text-teal-800">{msg}</p> : null}
      </form>
      <div className="card-panel rounded-2xl p-6">
        <h2 className="text-lg font-semibold">Offer stack</h2>
        <dl className="mt-4 space-y-2 text-sm">
          <div className="flex justify-between">
            <dt>ARV</dt>
            <dd>${result.arv.toLocaleString()}</dd>
          </div>
          <div className="flex justify-between">
            <dt>Rehab</dt>
            <dd>${result.rehab.toLocaleString()}</dd>
          </div>
          <div className="flex justify-between">
            <dt>Closing costs</dt>
            <dd>${result.closingCosts.toLocaleString()}</dd>
          </div>
          <div className="flex justify-between">
            <dt>Your fee</dt>
            <dd>${result.fee.toLocaleString()}</dd>
          </div>
          <div className="flex justify-between border-t border-teal-900/10 pt-2 text-base font-semibold">
            <dt>MAO / offer</dt>
            <dd>${result.offerPrice.toLocaleString()}</dd>
          </div>
        </dl>
      </div>
    </div>
  );
}

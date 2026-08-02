"use client";

import { FormEvent, useState } from "react";

type Contact = {
  id: string;
  kind: string;
  full_name: string;
  email: string | null;
  phone: string | null;
  company_name: string | null;
  created_at: string;
};

export function ContactsClient({
  initialContacts,
  canEdit = false,
}: {
  initialContacts: Contact[];
  canEdit?: boolean;
}) {
  const [contacts, setContacts] = useState(initialContacts);
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [kind, setKind] = useState("seller");
  const [msg, setMsg] = useState("");

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const res = await fetch("/api/contacts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        full_name: fullName,
        phone,
        email,
        kind,
      }),
    });
    const data = await res.json();
    if (!res.ok) {
      setMsg(data.error || "Failed");
      return;
    }
    setContacts((prev) => [data.contact, ...prev]);
    setFullName("");
    setPhone("");
    setEmail("");
    setMsg("Contact saved to this organization.");
  }

  return (
    <div className="space-y-6">
      {canEdit ? (
      <form onSubmit={onSubmit} className="card-panel grid gap-3 rounded-2xl p-5 md:grid-cols-2">
        <label className="text-sm font-medium">
          Full name
          <input
            className="input mt-1"
            required
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
          />
        </label>
        <label className="text-sm font-medium">
          Kind
          <select className="input mt-1" value={kind} onChange={(e) => setKind(e.target.value)}>
            <option value="seller">Seller</option>
            <option value="buyer">Buyer</option>
            <option value="agent">Agent</option>
            <option value="title">Title</option>
            <option value="other">Other</option>
          </select>
        </label>
        <label className="text-sm font-medium">
          Phone
          <input className="input mt-1" value={phone} onChange={(e) => setPhone(e.target.value)} />
        </label>
        <label className="text-sm font-medium">
          Email
          <input
            className="input mt-1"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>
        <div className="md:col-span-2">
          <button className="btn-primary" type="submit">
            Add contact
          </button>
        </div>
      </form>
      ) : null}
      {msg ? <p className="text-sm text-teal-800">{msg}</p> : null}
      <div className="card-panel overflow-x-auto rounded-2xl">
        <table className="min-w-full text-left text-sm">
          <thead className="border-b border-teal-900/10 text-teal-900/60">
            <tr>
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Kind</th>
              <th className="px-4 py-3">Phone</th>
              <th className="px-4 py-3">Email</th>
            </tr>
          </thead>
          <tbody>
            {contacts.map((c) => (
              <tr key={c.id} className="border-b border-teal-900/5">
                <td className="px-4 py-3">{c.full_name}</td>
                <td className="px-4 py-3">{c.kind}</td>
                <td className="px-4 py-3">{c.phone || "—"}</td>
                <td className="px-4 py-3">{c.email || "—"}</td>
              </tr>
            ))}
            {!contacts.length ? (
              <tr>
                <td className="px-4 py-6 text-teal-900/60" colSpan={4}>
                  No contacts yet.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}

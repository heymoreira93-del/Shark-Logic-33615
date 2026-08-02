"use client";

import { FormEvent, useState } from "react";

type Settings = {
  assignor_name: string;
  default_assignment_fee: number;
  default_emd: number;
  notify_phone: string;
  timezone: string;
};

export function SettingsClient({
  initialSettings,
  canWrite,
}: {
  initialSettings: Settings;
  canWrite: boolean;
}) {
  const [settings, setSettings] = useState(initialSettings);
  const [msg, setMsg] = useState("");

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!canWrite) return;
    const res = await fetch("/api/settings", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(settings),
    });
    const data = await res.json();
    if (!res.ok) {
      setMsg(data.error || "Failed");
      return;
    }
    setSettings(data.settings);
    setMsg("Settings saved for this organization.");
  }

  return (
    <form onSubmit={onSubmit} className="card-panel max-w-xl space-y-4 rounded-2xl p-6">
      <label className="block text-sm font-medium">
        Assignor name
        <input
          className="input mt-1"
          disabled={!canWrite}
          value={settings.assignor_name || ""}
          onChange={(e) => setSettings({ ...settings, assignor_name: e.target.value })}
        />
      </label>
      <label className="block text-sm font-medium">
        Default assignment fee
        <input
          className="input mt-1"
          type="number"
          disabled={!canWrite}
          value={settings.default_assignment_fee ?? 10000}
          onChange={(e) =>
            setSettings({ ...settings, default_assignment_fee: Number(e.target.value) })
          }
        />
      </label>
      <label className="block text-sm font-medium">
        Default EMD
        <input
          className="input mt-1"
          type="number"
          disabled={!canWrite}
          value={settings.default_emd ?? 2500}
          onChange={(e) => setSettings({ ...settings, default_emd: Number(e.target.value) })}
        />
      </label>
      <label className="block text-sm font-medium">
        Notify phone
        <input
          className="input mt-1"
          disabled={!canWrite}
          value={settings.notify_phone || ""}
          onChange={(e) => setSettings({ ...settings, notify_phone: e.target.value })}
        />
      </label>
      <label className="block text-sm font-medium">
        Timezone
        <input
          className="input mt-1"
          disabled={!canWrite}
          value={settings.timezone || "America/New_York"}
          onChange={(e) => setSettings({ ...settings, timezone: e.target.value })}
        />
      </label>
      {canWrite ? (
        <button className="btn-primary" type="submit">
          Save settings
        </button>
      ) : (
        <p className="text-sm text-teal-900/60">Read-only for your role.</p>
      )}
      {msg ? <p className="text-sm text-teal-800">{msg}</p> : null}
    </form>
  );
}

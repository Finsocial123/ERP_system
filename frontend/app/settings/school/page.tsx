"use client";

import { useEffect, useState } from "react";

import AppShell from "@/components/AppShell";
import { AppSection } from "@/components/CrudManager";
import { Button, Card, Input, Label, Textarea } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import type { School } from "@/types";

export default function SchoolSettingsPage() {
  const [form, setForm] = useState<Partial<School>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch<School>("/schools/me")
      .then(setForm)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load school"))
      .finally(() => setLoading(false));
  }, []);

  const update = (key: keyof School, value: string) => setForm((prev) => ({ ...prev, [key]: value }));

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setMessage("");
    setError("");
    try {
      const data = await apiFetch<School>("/schools/me", { method: "PUT", body: JSON.stringify(form) });
      setForm(data);
      setMessage("School profile updated successfully.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <AppShell>
      <AppSection title="School Profile" description="Manage basic institution details.">
        <Card>
          {loading ? <p className="text-sm text-slate-500">Loading...</p> : (
            <form onSubmit={save} className="grid gap-4 md:grid-cols-2">
              <div>
                <Label>Name</Label>
                <Input value={form.name || ""} onChange={(e) => update("name", e.target.value)} required />
              </div>
              <div>
                <Label>School / College Code</Label>
                <Input value={form.school_code || ""} onChange={(e) => update("school_code", e.target.value.toUpperCase())} />
                <p className="mt-1 text-xs text-slate-500">Users need this code on login.</p>
              </div>
              <div>
                <Label>Type</Label>
                <Input value={form.institution_type || ""} onChange={(e) => update("institution_type", e.target.value)} />
              </div>
              <div>
                <Label>Email</Label>
                <Input type="email" value={form.email || ""} onChange={(e) => update("email", e.target.value)} />
              </div>
              <div>
                <Label>Phone</Label>
                <Input value={form.phone || ""} onChange={(e) => update("phone", e.target.value)} />
              </div>
              <div className="md:col-span-2">
                <Label>Address</Label>
                <Textarea value={form.address || ""} onChange={(e) => update("address", e.target.value)} />
              </div>
              <div>
                <Label>City</Label>
                <Input value={form.city || ""} onChange={(e) => update("city", e.target.value)} />
              </div>
              <div>
                <Label>State</Label>
                <Input value={form.state || ""} onChange={(e) => update("state", e.target.value)} />
              </div>
              <div>
                <Label>Country</Label>
                <Input value={form.country || ""} onChange={(e) => update("country", e.target.value)} />
              </div>
              <div>
                <Label>Logo URL</Label>
                <Input value={form.logo_url || ""} onChange={(e) => update("logo_url", e.target.value)} />
              </div>
              {message && <p className="rounded-xl bg-green-50 px-3 py-2 text-sm text-green-700 md:col-span-2">{message}</p>}
              {error && <p className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700 md:col-span-2">{error}</p>}
              <div className="md:col-span-2">
                <Button type="submit" disabled={saving}>{saving ? "Saving..." : "Save Profile"}</Button>
              </div>
            </form>
          )}
        </Card>
      </AppSection>
    </AppShell>
  );
}

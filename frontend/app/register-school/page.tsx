"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { apiFetch, saveAuth } from "@/lib/api";
import type { AuthResponse } from "@/types";
import { AuthLink, Button, Card, Input, Label, Textarea } from "@/components/ui";

export default function RegisterSchoolPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    school_name: "",
    institution_type: "school",
    school_code: "",
    school_email: "",
    school_phone: "",
    address: "",
    city: "",
    state: "",
    country: "India",
    owner_name: "",
    owner_email: "",
    owner_phone: "",
    owner_password: "",
  });

  const update = (key: string, value: string) => setForm((prev) => ({ ...prev, [key]: value }));

  const register = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const payload = Object.fromEntries(Object.entries(form).map(([key, value]) => [key, value || null]));
      const data = await apiFetch<AuthResponse>("/auth/register-school", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      saveAuth(data);
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-slate-50 p-4 py-10">
      <Card className="mx-auto w-full max-w-4xl">
        <div className="mb-6">
          <p className="text-sm font-semibold uppercase tracking-wide text-slate-400">ERP SaaS Foundation</p>
          <h1 className="text-2xl font-bold text-slate-900">Register School / College</h1>
          <p className="mt-1 text-sm text-slate-500">Create institution account and first owner admin.</p>
        </div>

        <form onSubmit={register} className="grid gap-4 md:grid-cols-2">
          <div>
            <Label>Institution Name</Label>
            <Input value={form.school_name} onChange={(e) => update("school_name", e.target.value)} required placeholder="Green Valley School" />
          </div>
          <div>
            <Label>School / College Code</Label>
            <Input value={form.school_code} onChange={(e) => update("school_code", e.target.value.toUpperCase())} placeholder="DPS001" />
            <p className="mt-1 text-xs text-slate-500">Leave blank to auto-generate.</p>
          </div>
          <div>
            <Label>Institution Type</Label>
            <select className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm" value={form.institution_type} onChange={(e) => update("institution_type", e.target.value)}>
              <option value="school">School</option>
              <option value="college">College</option>
            </select>
          </div>
          <div>
            <Label>School Email</Label>
            <Input type="email" value={form.school_email} onChange={(e) => update("school_email", e.target.value)} placeholder="info@school.com" />
          </div>
          <div>
            <Label>School Phone</Label>
            <Input value={form.school_phone} onChange={(e) => update("school_phone", e.target.value)} placeholder="9876543210" />
          </div>
          <div className="md:col-span-2">
            <Label>Address</Label>
            <Textarea value={form.address} onChange={(e) => update("address", e.target.value)} placeholder="Full address" />
          </div>
          <div>
            <Label>City</Label>
            <Input value={form.city} onChange={(e) => update("city", e.target.value)} />
          </div>
          <div>
            <Label>State</Label>
            <Input value={form.state} onChange={(e) => update("state", e.target.value)} />
          </div>
          <div>
            <Label>Owner Name</Label>
            <Input value={form.owner_name} onChange={(e) => update("owner_name", e.target.value)} required placeholder="Admin name" />
          </div>
          <div>
            <Label>Owner Email</Label>
            <Input type="email" value={form.owner_email} onChange={(e) => update("owner_email", e.target.value)} required placeholder="admin@school.com" />
          </div>
          <div>
            <Label>Owner Phone</Label>
            <Input value={form.owner_phone} onChange={(e) => update("owner_phone", e.target.value)} />
          </div>
          <div>
            <Label>Password</Label>
            <Input type="password" value={form.owner_password} onChange={(e) => update("owner_password", e.target.value)} required minLength={6} placeholder="Minimum 6 characters" />
          </div>

          {error && <p className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700 md:col-span-2">{error}</p>}

          <div className="flex items-center gap-4 md:col-span-2">
            <Button type="submit" disabled={loading}>{loading ? "Creating..." : "Create Institution"}</Button>
            <p className="text-sm text-slate-500">Already registered? <AuthLink href="/login">Login</AuthLink></p>
          </div>
        </form>
      </Card>
    </main>
  );
}

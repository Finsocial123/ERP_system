"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { apiFetch, saveAuth } from "@/lib/api";
import type { AuthResponse } from "@/types";
import { AuthLink, Button, Card, Input, Label, Textarea } from "@/components/ui";

type OtpResponse = {
  message: string;
  owner_email: string;
  expires_in_minutes: number;
  debug_otp?: string | null;
};

export default function RegisterSchoolPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [error, setError] = useState("");
  const [otpResponse, setOtpResponse] = useState<OtpResponse | null>(null);
  const [otp, setOtp] = useState("");
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

  const requestOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    setOtpResponse(null);
    try {
      const payload = Object.fromEntries(Object.entries(form).map(([key, value]) => [key, value || null]));
      const data = await apiFetch<OtpResponse>("/auth/register-school", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setOtpResponse(data);
      setOtp("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setLoading(false);
    }
  };

  const verifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setVerifying(true);
    setError("");
    try {
      const data = await apiFetch<AuthResponse>("/auth/verify-school-registration", {
        method: "POST",
        body: JSON.stringify({ owner_email: form.owner_email, otp }),
      });
      saveAuth(data);
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "OTP verification failed");
    } finally {
      setVerifying(false);
    }
  };

  return (
    <main className="min-h-screen bg-slate-50 p-4 py-10">
      <Card className="mx-auto w-full max-w-4xl">
        <div className="mb-6">
          <p className="text-sm font-semibold uppercase tracking-wide text-slate-400">ERP SaaS Foundation</p>
          <h1 className="text-2xl font-bold text-slate-900">Register School / College</h1>
          <p className="mt-1 text-sm text-slate-500">Create institution account and verify owner email before the school is created.</p>
        </div>

        {!otpResponse ? (
          <form onSubmit={requestOtp} className="grid gap-4 md:grid-cols-2">
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
              <p className="mt-1 text-xs text-slate-500">OTP will be sent to this email.</p>
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
              <Button type="submit" disabled={loading}>{loading ? "Sending OTP..." : "Send Verification OTP"}</Button>
              <p className="text-sm text-slate-500">Already registered? <AuthLink href="/login">Login</AuthLink></p>
            </div>
          </form>
        ) : (
          <form onSubmit={verifyOtp} className="mx-auto max-w-md space-y-4 rounded-2xl border border-slate-200 bg-white p-5">
            <div>
              <h2 className="text-lg font-bold text-slate-900">Verify owner email</h2>
              <p className="mt-1 text-sm text-slate-500">{otpResponse.message}</p>
              <p className="mt-1 text-xs text-slate-500">Email: {otpResponse.owner_email}</p>
            </div>
            <div>
              <Label>Enter OTP</Label>
              <Input value={otp} onChange={(e) => setOtp(e.target.value.replace(/\D/g, "").slice(0, 6))} required placeholder="6 digit OTP" />
              <p className="mt-1 text-xs text-slate-500">OTP expires in {otpResponse.expires_in_minutes} minutes.</p>
            </div>
            {otpResponse.debug_otp && (
              <div className="rounded-xl bg-amber-50 p-3 text-sm text-amber-800">
                <p className="font-semibold">Debug OTP:</p>
                <p className="text-lg tracking-[0.25em]">{otpResponse.debug_otp}</p>
                <p className="mt-1 text-xs">Set EMAIL_OTP_DEBUG=false after SMTP is configured.</p>
              </div>
            )}
            {error && <p className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
            <Button type="submit" disabled={verifying} className="w-full">{verifying ? "Verifying..." : "Verify & Create Institution"}</Button>
            <button type="button" onClick={() => setOtpResponse(null)} className="w-full text-sm font-semibold text-slate-600 underline underline-offset-4">
              Edit registration details
            </button>
          </form>
        )}
      </Card>
    </main>
  );
}

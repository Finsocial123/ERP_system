"use client";

import Link from "next/link";
import { useState } from "react";

import { Button, Card, Input, Label } from "@/components/ui";
import { apiFetch } from "@/lib/api";

type ForgotResponse = {
  message: string;
  reset_token?: string | null;
  reset_url?: string | null;
};

export default function ForgotPasswordPage() {
  const [schoolCode, setSchoolCode] = useState("");
  const [loginId, setLoginId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [response, setResponse] = useState<ForgotResponse | null>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    setResponse(null);
    setLoading(true);
    try {
      const data = await apiFetch<ForgotResponse>("/auth/forgot-password", {
        method: "POST",
        body: JSON.stringify({ school_code: schoolCode, login_id: loginId }),
      });
      setResponse(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start password reset");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 p-4">
      <Card className="w-full max-w-md">
        <p className="text-sm font-semibold uppercase tracking-wide text-slate-400">School ERP</p>
        <h1 className="text-2xl font-bold text-slate-900">Forgot Password</h1>
        <p className="mt-1 text-sm text-slate-500">Enter your school code and login ID. A secure password reset link will be sent to the registered email.</p>
        <form onSubmit={submit} className="mt-6 space-y-4">
          <div><Label>School / College Code</Label><Input value={schoolCode} onChange={(e) => setSchoolCode(e.target.value.toUpperCase())} required placeholder="DPS001" /></div>
          <div><Label>Email / Employee ID / Admission No.</Label><Input value={loginId} onChange={(e) => setLoginId(e.target.value)} required placeholder="EMP102 or STU2026001" /></div>
          {error && <p className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
          <Button type="submit" disabled={loading} className="w-full">{loading ? "Sending..." : "Send Reset Link"}</Button>
        </form>
        {response && (
          <div className="mt-5 rounded-xl bg-green-50 p-4 text-sm text-green-800">
            <p>{response.message}</p>
            {response.reset_token && (
              <div className="mt-3 rounded-lg bg-white p-3 text-slate-700">
                <p className="font-semibold">Debug reset token:</p>
                <p className="break-all text-xs">{response.reset_token}</p>
                <Link href={`/reset-password?token=${response.reset_token}`} className="mt-2 inline-block font-semibold underline underline-offset-4">Open reset page</Link>
                <p className="mt-2 text-xs text-slate-500">Set EMAIL_OTP_DEBUG=false after SMTP is configured.</p>
              </div>
            )}
          </div>
        )}
        <p className="mt-5 text-center text-sm text-slate-500"><Link href="/login" className="font-semibold text-slate-900 underline underline-offset-4">Back to login</Link></p>
      </Card>
    </main>
  );
}

"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Button, Card, Input, Label } from "@/components/ui";
import { apiFetch } from "@/lib/api";

export default function ResetPasswordPage() {
  const [token, setToken] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setToken(params.get("token") || "");
  }, []);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    setSuccess("");
    if (newPassword !== confirmPassword) {
      setError("New password and confirm password do not match");
      return;
    }
    setLoading(true);
    try {
      await apiFetch("/auth/reset-password", { method: "POST", body: JSON.stringify({ token, new_password: newPassword }) });
      setSuccess("Password reset successfully. You can login now.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Password reset failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 p-4">
      <Card className="w-full max-w-md">
        <p className="text-sm font-semibold uppercase tracking-wide text-slate-400">School ERP</p>
        <h1 className="text-2xl font-bold text-slate-900">Reset Password</h1>
        <p className="mt-1 text-sm text-slate-500">Use the secure reset link sent to your registered email.</p>
        <form onSubmit={submit} className="mt-6 space-y-4">
          <div><Label>Reset Link Token</Label><Input value={token} onChange={(e) => setToken(e.target.value)} required /></div>
          <div><Label>New Password</Label><Input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} required minLength={6} /></div>
          <div><Label>Confirm New Password</Label><Input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} required minLength={6} /></div>
          {error && <p className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
          {success && <p className="rounded-xl bg-green-50 px-3 py-2 text-sm text-green-700">{success}</p>}
          <Button type="submit" disabled={loading} className="w-full">{loading ? "Resetting..." : "Reset Password"}</Button>
        </form>
        <p className="mt-5 text-center text-sm text-slate-500"><Link href="/login" className="font-semibold text-slate-900 underline underline-offset-4">Back to login</Link></p>
      </Card>
    </main>
  );
}

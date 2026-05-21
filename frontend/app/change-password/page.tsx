"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import AppShell from "@/components/AppShell";
import { AppSection } from "@/components/CrudManager";
import { Button, Card, Input, Label } from "@/components/ui";
import { apiFetch, dashboardPathForRole, getSavedAuth, saveAuth } from "@/lib/api";
import type { AuthResponse } from "@/types";

export default function ChangePasswordPage() {
  const router = useRouter();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

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
      await apiFetch("/auth/change-password", {
        method: "POST",
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      });
      const me = await apiFetch<AuthResponse>("/auth/me");
      saveAuth(me);
      setSuccess("Password changed successfully");
      router.replace(dashboardPathForRole(me.user.role, false));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Password change failed");
    } finally {
      setLoading(false);
    }
  };

  const saved = getSavedAuth();

  return (
    <AppShell>
      <AppSection title="Change Password" description="Required for first login accounts created by admin.">
        <Card className="max-w-xl">
          {saved?.user.must_change_password && (
            <p className="mb-4 rounded-xl bg-amber-50 px-3 py-2 text-sm text-amber-700">For security, create your own password before using the portal.</p>
          )}
          <form onSubmit={submit} className="space-y-4">
            <div><Label>Current Password</Label><Input type="password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} required /></div>
            <div><Label>New Password</Label><Input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} required minLength={6} /></div>
            <div><Label>Confirm New Password</Label><Input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} required minLength={6} /></div>
            {error && <p className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
            {success && <p className="rounded-xl bg-green-50 px-3 py-2 text-sm text-green-700">{success}</p>}
            <Button type="submit" disabled={loading}>{loading ? "Changing..." : "Change Password"}</Button>
          </form>
        </Card>
      </AppSection>
    </AppShell>
  );
}

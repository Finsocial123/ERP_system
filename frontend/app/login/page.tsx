"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Eye, EyeOff, School } from "lucide-react";

import { apiFetch, dashboardPathForRole, saveAuth } from "@/lib/api";
import type { AuthResponse } from "@/types";
import { AuthLink, Button, Card, Input, Label } from "@/components/ui";

const portalTabs = ["Admin", "Teacher", "Student", "Parent"];

export default function LoginPage() {
  const router = useRouter();
  const [schoolCode, setSchoolCode] = useState("");
  const [loginId, setLoginId] = useState("");
  const [password, setPassword] = useState("");
  const [activeTab, setActiveTab] = useState("Admin");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const login = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const data = await apiFetch<AuthResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ school_code: schoolCode, login_id: loginId, password }),
      });
      saveAuth(data);
      router.replace(dashboardPathForRole(data.user.role, Boolean(data.user.must_change_password)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-50 via-white to-slate-100 p-4">
      <Card className="w-full max-w-lg border-slate-200/80 p-0 shadow-lg">
        <div className="rounded-t-2xl bg-slate-900 p-6 text-white">
          <div className="mb-5 flex items-center gap-3">
            <div className="rounded-2xl bg-white/10 p-3">
              <School size={24} />
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.25em] text-slate-300">School ERP</p>
              <h1 className="text-2xl font-bold">Welcome back</h1>
            </div>
          </div>
          <p className="text-sm text-slate-300">Login to your school, college, teacher, student or parent portal.</p>
        </div>

        <div className="p-6">
          <div className="mb-5 grid grid-cols-4 gap-2 rounded-2xl bg-slate-100 p-1">
            {portalTabs.map((tab) => (
              <button
                key={tab}
                type="button"
                onClick={() => setActiveTab(tab)}
                className={`rounded-xl px-2 py-2 text-xs font-semibold transition ${activeTab === tab ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-900"}`}
              >
                {tab}
              </button>
            ))}
          </div>

          <form onSubmit={login} className="space-y-4">
            <div>
              <Label>School / College Code</Label>
              <Input value={schoolCode} onChange={(e) => setSchoolCode(e.target.value.toUpperCase())} required placeholder="Example: DPS001" />
              <p className="mt-1 text-xs text-slate-500">Ask your institution admin for this code.</p>
            </div>
            <div>
              <Label>Email / Employee ID / Admission No.</Label>
              <Input value={loginId} onChange={(e) => setLoginId(e.target.value)} required placeholder={activeTab === "Student" ? "STU2026001" : activeTab === "Teacher" ? "EMP102 or teacher@email.com" : "admin@school.com"} />
            </div>
            <div>
              <div className="flex items-center justify-between">
                <Label>Password</Label>
                <Link href="/forgot-password" className="text-xs font-semibold text-slate-700 underline underline-offset-4">
                  Forgot password?
                </Link>
              </div>
              <div className="relative">
                <Input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  placeholder="••••••••"
                  className="pr-10"
                />
                <button type="button" onClick={() => setShowPassword((prev) => !prev)} className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-700">
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>
            {error && <p className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
            <Button type="submit" disabled={loading} className="w-full py-3">{loading ? "Logging in..." : "Continue to Portal"}</Button>
          </form>
          <p className="mt-5 text-center text-sm text-slate-500">
            New institution? <AuthLink href="/register-school">Register school</AuthLink>
          </p>
        </div>
      </Card>
    </main>
  );
}

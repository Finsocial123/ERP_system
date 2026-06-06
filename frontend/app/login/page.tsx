"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Eye, EyeOff, School } from "lucide-react";

import { apiFetch, dashboardPathForRole, fileUrl, saveAuth } from "@/lib/api";
import { applyBrandingTheme, cacheBrandingTheme, DEFAULT_BRANDING } from "@/lib/branding";
import type { AuthResponse, SchoolBrandingPublic } from "@/types";
import { AuthLink, Button, Card, Input, Label } from "@/components/ui";

const portalTabs = ["Admin", "Teacher", "Student", "Parent"] as const;

type PortalTab = (typeof portalTabs)[number];

const loginPlaceholders: Record<PortalTab, string> = {
  Admin: "admin@school.com",
  Teacher: "EMP102 or teacher@email.com",
  Student: "STU2026001",
  Parent: "parent@email.com / phone / STU2026001-PARENT",
};

export default function LoginPage() {
  const router = useRouter();
  const [schoolCode, setSchoolCode] = useState("");
  const [loginId, setLoginId] = useState("");
  const [password, setPassword] = useState("");
  const [activeTab, setActiveTab] = useState<PortalTab>("Admin");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [brandingPreview, setBrandingPreview] =
    useState<SchoolBrandingPublic | null>(null);

  useEffect(() => {
    const code = schoolCode.trim().toUpperCase();
    if (code.length < 3) {
      setBrandingPreview(null);
      applyBrandingTheme(DEFAULT_BRANDING);
      return;
    }

    const timer = window.setTimeout(() => {
      apiFetch<SchoolBrandingPublic>(
        `/schools/branding/by-code/${encodeURIComponent(code)}`,
      )
        .then((data) => {
          setBrandingPreview(data);
          applyBrandingTheme(data);
          cacheBrandingTheme(data); // ← persist so AppShell finds it instantly after login redirect
        })
        .catch(() => {
          setBrandingPreview(null);
          applyBrandingTheme(DEFAULT_BRANDING);
        });
    }, 450);

    return () => window.clearTimeout(timer);
  }, [schoolCode]);

  const previewLogo = fileUrl(brandingPreview?.logo_url);
  const previewName = brandingPreview?.school_name || "School ERP";

  const login = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const data = await apiFetch<AuthResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify({
          school_code: schoolCode,
          login_id: loginId,
          password,
          selected_role: activeTab.toUpperCase(),
        }),
      });
      saveAuth(data);
      router.replace(
        dashboardPathForRole(
          data.user.role,
          Boolean(data.user.must_change_password),
        ),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main
      className="flex min-h-screen items-center justify-center p-4"
      style={{
        background:
          "linear-gradient(135deg, var(--erp-background, #f8fafc), #ffffff, var(--erp-primary-soft, #dbeafe))",
      }}
    >
      <Card className="w-full max-w-lg border-slate-200/80 p-0 shadow-lg">
        <div
          className="rounded-t-2xl p-6 text-white"
          style={{ background: "var(--erp-sidebar, #0f172a)" }}
        >
          <div className="mb-5 flex items-center gap-3">
            <div
              className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white/95 p-2"
              style={{ color: "var(--erp-primary, #2563eb)" }}
            >
              {previewLogo ? (
                <img
                  src={previewLogo}
                  alt={`${previewName} logo`}
                  className="max-h-full max-w-full object-contain"
                />
              ) : (
                <School size={24} />
              )}
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.25em] text-slate-300">
                {previewName}
              </p>
              <h1 className="text-2xl font-bold">Welcome back</h1>
            </div>
          </div>
          <p className="text-sm text-slate-300">
            Login to your school, college, teacher, student or parent portal.
          </p>
        </div>

        <div className="p-6">
          <div className="mb-5 grid grid-cols-4 gap-2 rounded-2xl bg-slate-100 p-1">
            {portalTabs.map((tab) => (
              <button
                key={tab}
                type="button"
                onClick={() => setActiveTab(tab)}
                className={`rounded-xl px-2 py-2 text-xs font-semibold transition ${activeTab === tab ? "bg-white shadow-sm" : "text-slate-500 hover:text-slate-900"}`}
                style={
                  activeTab === tab
                    ? { color: "var(--erp-primary, #0f172a)" }
                    : undefined
                }
              >
                {tab}
              </button>
            ))}
          </div>

          <form onSubmit={login} className="space-y-4">
            <div>
              <Label>School / College Code</Label>
              <Input
                value={schoolCode}
                onChange={(e) => setSchoolCode(e.target.value.toUpperCase())}
                required
                placeholder="Example: DPS001"
              />
              <p className="mt-1 text-xs text-slate-500">
                {brandingPreview
                  ? `Theme loaded for ${brandingPreview.school_name}.`
                  : "Ask your institution admin for this code."}
              </p>
            </div>
            <div>
              <Label>Email / Employee ID / Admission No.</Label>
              <Input
                value={loginId}
                onChange={(e) => setLoginId(e.target.value)}
                required
                placeholder={loginPlaceholders[activeTab]}
              />
              <p className="mt-1 text-xs text-slate-500">
                The selected tab must match the account role.
              </p>
            </div>
            <div>
              <div className="flex items-center justify-between">
                <Label>Password</Label>
                <Link
                  href="/forgot-password"
                  className="text-xs font-semibold text-slate-700 underline underline-offset-4"
                >
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
                <button
                  type="button"
                  onClick={() => setShowPassword((prev) => !prev)}
                  className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-700"
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>
            {error && (
              <p className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">
                {error}
              </p>
            )}
            <Button type="submit" disabled={loading} className="w-full py-3">
              {loading ? "Logging in..." : "Continue to Portal"}
            </Button>
          </form>
          <p className="mt-5 text-center text-sm text-slate-500">
            New institution?{" "}
            <AuthLink href="/register-school">Register school</AuthLink>
          </p>
        </div>
      </Card>
    </main>
  );
}

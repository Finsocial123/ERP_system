"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  BookOpen,
  Building2,
  CalendarCheck,
  ClipboardList,
  CreditCard,
  GraduationCap,
  Home,
  LayoutDashboard,
  LogOut,
  Menu,
  School,
  Settings,
  UserRound,
  Users,
  X,
} from "lucide-react";

import { clearAuth, dashboardPathForRole, getSavedAuth } from "@/lib/api";
import type { AuthResponse } from "@/types";

type NavItem = {
  href: string;
  label: string;
  icon: typeof LayoutDashboard;
  roles: string[];
};

const ADMIN_ROLES = ["SUPER_ADMIN", "SCHOOL_OWNER", "SCHOOL_ADMIN"];

const navItems: NavItem[] = [
  // ── Admin ──────────────────────────────────────────────────────────────────
  { href: "/dashboard",               label: "Admin Dashboard",     icon: LayoutDashboard, roles: ADMIN_ROLES },
  { href: "/students",                label: "Students",            icon: Users,           roles: ADMIN_ROLES },
  { href: "/teachers",                label: "Teachers",            icon: UserRound,       roles: ADMIN_ROLES },
  { href: "/homework", label: "Homework", icon: ClipboardList, roles: ADMIN_ROLES },
  { href: "/attendance",              label: "Attendance",          icon: CalendarCheck,   roles: ADMIN_ROLES },
  { href: "/settings/school",         label: "School Profile",      icon: School,          roles: ADMIN_ROLES },
  { href: "/setup/academic-sessions", label: "Academic Sessions",   icon: GraduationCap,   roles: ADMIN_ROLES },
  { href: "/setup/departments",       label: "Departments",         icon: Building2,       roles: ADMIN_ROLES },
  { href: "/setup/classes",           label: "Classes",             icon: Settings,        roles: ADMIN_ROLES },
  { href: "/setup/sections",          label: "Sections",            icon: Settings,        roles: ADMIN_ROLES },
  { href: "/setup/subjects",          label: "Subjects",            icon: BookOpen,        roles: ADMIN_ROLES },

  { href: "/teacher-dashboard", label: "Teacher Dashboard", icon: LayoutDashboard, roles: ["TEACHER"] },
  { href: "/teacher-dashboard", label: "My Classes", icon: Home, roles: ["TEACHER"] },
  { href: "/teacher-dashboard", label: "Attendance", icon: CalendarCheck, roles: ["TEACHER"] },
  { href: "/teacher-homework", label: "Homework", icon: ClipboardList, roles: ["TEACHER"] },

  { href: "/student-dashboard", label: "Student Dashboard", icon: LayoutDashboard, roles: ["STUDENT"] },
  { href: "/student-homework", label: "Homework", icon: ClipboardList, roles: ["STUDENT"] },
  { href: "/student-dashboard", label: "Attendance", icon: CalendarCheck, roles: ["STUDENT"] },
  { href: "/student-dashboard", label: "Fees", icon: CreditCard, roles: ["STUDENT"] },

  // ── Parent ─────────────────────────────────────────────────────────────────
  { href: "/parent-dashboard",        label: "Dashboard",           icon: LayoutDashboard, roles: ["PARENT"] },
  { href: "/parent-homework", label: "Homework", icon: ClipboardList, roles: ["PARENT"] },
  { href: "/attendance/my",           label: "Child Attendance",    icon: CalendarCheck,   roles: ["PARENT"] },
  { href: "/fees",                    label: "Fees",                icon: CreditCard,      roles: ["PARENT"] },
];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [auth, setAuth] = useState<AuthResponse | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const saved = getSavedAuth();
    if (!saved) {
      router.replace("/login");
      return;
    }
    if (saved.user.must_change_password && pathname !== "/change-password") {
      router.replace("/change-password");
      return;
    }
    const protectedPaths = new Set(navItems.map((item) => item.href));
    if (protectedPaths.has(pathname)) {
      const canOpenPath = navItems.some(
        (item) => item.href === pathname && item.roles.includes(saved.user.role)
      );
      if (!canOpenPath) {
        router.replace(
          dashboardPathForRole(saved.user.role, Boolean(saved.user.must_change_password))
        );
        return;
      }
    }
    setAuth(saved);
  }, [pathname, router]);

  const visibleNav = useMemo(() => {
    if (!auth) return [];
    return navItems.filter((item) => item.roles.includes(auth.user.role));
  }, [auth]);

  const logout = () => {
    clearAuth();
    router.replace("/login");
  };

  if (!auth)
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-600">
        Loading...
      </div>
    );

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 w-72 border-r border-slate-200 bg-white p-4 transition lg:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="mb-6 flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              ERP Portal
            </p>
            <h1 className="text-lg font-bold text-slate-900">
              {auth.school?.name || "School ERP"}
            </h1>
            {auth.school?.school_code && (
              <p className="mt-1 text-xs text-slate-500">
                Code: {auth.school.school_code}
              </p>
            )}
          </div>
          <button className="lg:hidden" onClick={() => setOpen(false)}>
            <X size={22} />
          </button>
        </div>

        <nav className="space-y-1">
          {visibleNav.map((item, index) => {
            const Icon = item.icon;
            const active = pathname === item.href;
            return (
              <Link
                key={`${item.href}-${item.label}-${index}`}
                href={item.href}
                onClick={() => setOpen(false)}
                className={`flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition ${
                  active
                    ? "bg-slate-900 text-white"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                }`}
              >
                <Icon size={18} />
                {item.label}
              </Link>
            );
          })}
        </nav>
      </aside>

      {/* Main content */}
      <div className="lg:pl-72">
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-slate-200 bg-white/90 px-4 backdrop-blur lg:px-8">
          <button
            className="rounded-xl border border-slate-200 p-2 lg:hidden"
            onClick={() => setOpen(true)}
          >
            <Menu size={20} />
          </button>
          <button
            type="button"
            onClick={() =>
              router.replace(
                dashboardPathForRole(
                  auth.user.role,
                  Boolean(auth.user.must_change_password)
                )
              )
            }
            className="hidden text-left lg:block"
          >
            <p className="text-sm font-semibold text-slate-900">
              {auth.user.full_name}
            </p>
            <p className="text-xs text-slate-500">
              {auth.user.role} · {auth.user.login_id}
            </p>
          </button>
          <button
            onClick={logout}
            className="flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
          >
            <LogOut size={16} /> Logout
          </button>
        </header>
        <main className="p-4 lg:p-8">{children}</main>
      </div>
    </div>
  );
}
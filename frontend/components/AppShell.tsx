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
  FileText,
  GraduationCap,
  LayoutDashboard,
  Library,
  LogOut,
  Menu,
  NotebookIcon,
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
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, roles: ADMIN_ROLES },
  { href: "/students", label: "Students", icon: Users, roles: ADMIN_ROLES },
  { href: "/teachers", label: "Teachers", icon: UserRound, roles: ADMIN_ROLES },
  { href: "/homework", label: "Homework", icon: ClipboardList, roles: ADMIN_ROLES },
  { href: "/timetable", label: "Timetable", icon: CalendarCheck, roles: ADMIN_ROLES },
  { href: "/exams", label: "Exams & Results", icon: GraduationCap, roles: ADMIN_ROLES },
  { href: "/fees", label: "Fee Management", icon: CreditCard, roles: ADMIN_ROLES },
  { href: "/attendance", label: "Attendance", icon: CalendarCheck, roles: ADMIN_ROLES },
  { href: "/library", label: "Library", icon: Library, roles: ADMIN_ROLES },
  { href: "/reports", label: "Reports", icon: FileText, roles: ADMIN_ROLES },
  { href: "/settings/school", label: "School Profile", icon: School, roles: ADMIN_ROLES },
  { href: "/setup/academic-sessions", label: "Academic Sessions", icon: GraduationCap, roles: ADMIN_ROLES },
  { href: "/setup/departments", label: "Departments", icon: Building2, roles: ADMIN_ROLES },
  { href: "/setup/classes", label: "Classes", icon: Settings, roles: ADMIN_ROLES },
  { href: "/setup/sections", label: "Sections", icon: Settings, roles: ADMIN_ROLES },
  { href: "/setup/subjects", label: "Subjects", icon: BookOpen, roles: ADMIN_ROLES },
  { href: "/setup/notice", label: "Notices", icon: NotebookIcon, roles: ADMIN_ROLES },
  

  { href: "/teacher-dashboard", label: "Dashboard", icon: LayoutDashboard, roles: ["TEACHER"] },
  { href: "/attendance", label: "Attendance", icon: CalendarCheck, roles: ["TEACHER"] },
  { href: "/teacher-homework", label: "Homework", icon: ClipboardList, roles: ["TEACHER"] },
  { href: "/teacher-timetable", label: "Timetable", icon: CalendarCheck, roles: ["TEACHER"] },
  { href: "/teacher-exams", label: "Exams & Marks", icon: GraduationCap, roles: ["TEACHER"] },
  { href: "/teachers/curriculum", label: "Curriculum", icon: NotebookIcon, roles: ["TEACHER"] },
  { href: "/teachers/notice", label: "Notices", icon: NotebookIcon, roles: ["TEACHER"] },
  { href: "/library", label: "Library", icon: Library, roles: ["TEACHER"] },

  { href: "/student-dashboard", label: "Dashboard", icon: LayoutDashboard, roles: ["STUDENT"] },
  { href: "/attendance/my", label: "My Attendance", icon: CalendarCheck, roles: ["STUDENT"] },
  { href: "/student-homework", label: "Homework", icon: ClipboardList, roles: ["STUDENT"] },
  { href: "/student-timetable", label: "Timetable", icon: CalendarCheck, roles: ["STUDENT"] },
  { href: "/student-exams", label: "Report Cards", icon: GraduationCap, roles: ["STUDENT"] },
  { href: "/students/notice", label: "Notices", icon: NotebookIcon, roles: ["STUDENT"] },
  { href: "/fees", label: "Fees", icon: CreditCard, roles: ["STUDENT"] },
  { href: "/library", label: "Library", icon: Library, roles: ["STUDENT"] },

  { href: "/parent-dashboard", label: "Dashboard", icon: LayoutDashboard, roles: ["PARENT"] },
  { href: "/parent-homework", label: "Homework", icon: ClipboardList, roles: ["PARENT"] },
  { href: "/parent-timetable", label: "Timetable", icon: CalendarCheck, roles: ["PARENT"] },
  { href: "/parent-exams", label: "Child Results", icon: GraduationCap, roles: ["PARENT"] },
  { href: "/parents/notice", label: "Notices", icon: NotebookIcon, roles: ["PARENT"] },
  { href: "/attendance/my", label: "Child Attendance", icon: CalendarCheck, roles: ["PARENT"] },
  { href: "/fees", label: "Child Fees", icon: CreditCard, roles: ["PARENT"] },
  { href: "/communication", label: "Communication", icon: NotebookIcon, roles: [...ADMIN_ROLES, "TEACHER", "STUDENT", "PARENT"] },
];

function formatRole(value: string) {
  return value
    .toLowerCase()
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [auth, setAuth] = useState<AuthResponse | null>(null);
  const [open, setOpen] = useState(false);
  const [desktopSidebarOpen, setDesktopSidebarOpen] = useState(true);

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
      const canOpenPath = navItems.some((item) => item.href === pathname && item.roles.includes(saved.user.role));
      if (!canOpenPath) {
        router.replace(dashboardPathForRole(saved.user.role, Boolean(saved.user.must_change_password)));
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

  if (!auth) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 text-slate-600">
        Loading...
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-72 flex-col border-r border-slate-200 bg-white transition-transform duration-200 ${
          open ? "translate-x-0" : "-translate-x-full"
        } ${desktopSidebarOpen ? "lg:translate-x-0" : "lg:-translate-x-full"}`}
      >
        <div className="border-b border-slate-100 p-4">
          <div className="flex items-start justify-between gap-3">
            <button
              type="button"
              onClick={() => router.replace(dashboardPathForRole(auth.user.role, Boolean(auth.user.must_change_password)))}
              className="min-w-0 text-left"
            >
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">ERP Portal</p>
              <h1 className="mt-1 truncate text-lg font-bold text-slate-900">{auth.school?.name || "School ERP"}</h1>
              {auth.school?.school_code && <p className="mt-1 text-xs text-slate-500">Code: {auth.school.school_code}</p>}
            </button>
            <button className="rounded-xl p-2 text-slate-500 hover:bg-slate-100 lg:hidden" onClick={() => setOpen(false)} aria-label="Close sidebar">
              <X size={20} />
            </button>
          </div>
        </div>

        <nav className="custom-scrollbar min-h-0 flex-1 space-y-1 overflow-y-auto p-3">
          {visibleNav.map((item, index) => {
            const Icon = item.icon;
            const active = pathname === item.href;
            return (
              <Link
                key={`${item.href}-${item.label}-${index}`}
                href={item.href}
                onClick={() => setOpen(false)}
                className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition ${
                  active
                    ? "bg-slate-900 text-white shadow-sm"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                }`}
              >
                <Icon size={18} />
                <span className="truncate">{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="border-t border-slate-100 p-4">
          <div className="rounded-2xl bg-slate-50 p-3">
            <p className="truncate text-sm font-semibold text-slate-900">{auth.user.full_name}</p>
            <p className="mt-1 truncate text-xs text-slate-500">{formatRole(auth.user.role)}</p>
          </div>
        </div>
      </aside>

      {open && <button className="fixed inset-0 z-30 bg-slate-900/30 lg:hidden" onClick={() => setOpen(false)} aria-label="Close menu overlay" />}

      <div className={`transition-all duration-200 ${desktopSidebarOpen ? "lg:pl-72" : "lg:pl-0"}`}>
        <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-slate-200 bg-white/90 px-4 backdrop-blur lg:px-8">
          <div className="flex items-center gap-3">
            <button
              className="rounded-xl border border-slate-200 p-2 text-slate-700 hover:bg-slate-100 lg:hidden"
              onClick={() => setOpen(true)}
              aria-label="Open sidebar"
            >
              <Menu size={20} />
            </button>
            <button
              className="hidden items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100 lg:inline-flex"
              onClick={() => setDesktopSidebarOpen((prev) => !prev)}
              aria-label={desktopSidebarOpen ? "Hide sidebar" : "Show sidebar"}
            >
              <Menu size={18} />
              <span>{desktopSidebarOpen ? "Hide menu" : "Show menu"}</span>
            </button>
            <button
              type="button"
              onClick={() => router.replace(dashboardPathForRole(auth.user.role, Boolean(auth.user.must_change_password)))}
              className="hidden text-left md:block"
            >
              <p className="text-sm font-semibold text-slate-900">{auth.user.full_name}</p>
              <p className="text-xs text-slate-500">{formatRole(auth.user.role)} · {auth.user.login_id}</p>
            </button>
          </div>

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

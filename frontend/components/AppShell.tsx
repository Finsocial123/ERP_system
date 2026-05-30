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
  Video,
  Album,
  Presentation,
  ChevronRight,
} from "lucide-react";

import { clearAuth, dashboardPathForRole, getSavedAuth } from "@/lib/api";
import type { AuthResponse } from "@/types";

type NavItem = {
  href: string;
  label: string;
  icon: typeof LayoutDashboard;
  roles: string[];
  group?: string;
};

const ADMIN_ROLES = ["SUPER_ADMIN", "SCHOOL_OWNER", "SCHOOL_ADMIN"];

const navItems: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, roles: ADMIN_ROLES, group: "Main" },
  { href: "/profile", label: "My Profile", icon: UserRound, roles: ADMIN_ROLES, group: "Main" },
  { href: "/students", label: "Students", icon: Users, roles: ADMIN_ROLES, group: "People" },
  { href: "/teachers", label: "Teachers", icon: UserRound, roles: ADMIN_ROLES, group: "People" },
  { href: "/homework", label: "Homework", icon: ClipboardList, roles: ADMIN_ROLES, group: "Academic" },
  { href: "/courses", label: "LMS Courses", icon: BookOpen, roles: ADMIN_ROLES, group: "Academic" },
  { href: "/timetable", label: "Timetable", icon: CalendarCheck, roles: ADMIN_ROLES, group: "Academic" },
  { href: "/exams", label: "Exams & Results", icon: GraduationCap, roles: ADMIN_ROLES, group: "Academic" },
  { href: "/fees", label: "Fee Management", icon: CreditCard, roles: ADMIN_ROLES, group: "Finance" },
  { href: "/attendance", label: "Attendance", icon: CalendarCheck, roles: ADMIN_ROLES, group: "Academic" },
  { href: "/library", label: "Library", icon: Library, roles: ADMIN_ROLES, group: "Resources" },
  { href: "/reports", label: "Reports", icon: FileText, roles: ADMIN_ROLES, group: "Resources" },
  { href: "/settings/school", label: "School Profile", icon: School, roles: ADMIN_ROLES, group: "Setup" },
  { href: "/setup/academic-sessions", label: "Academic Sessions", icon: GraduationCap, roles: ADMIN_ROLES, group: "Setup" },
  { href: "/setup/departments", label: "Departments", icon: Building2, roles: ADMIN_ROLES, group: "Setup" },
  { href: "/setup/classes", label: "Classes", icon: Settings, roles: ADMIN_ROLES, group: "Setup" },
  { href: "/setup/sections", label: "Sections", icon: Settings, roles: ADMIN_ROLES, group: "Setup" },
  { href: "/setup/subjects", label: "Subjects", icon: BookOpen, roles: ADMIN_ROLES, group: "Setup" },
  { href: "/setup/notice", label: "Notices", icon: NotebookIcon, roles: ADMIN_ROLES, group: "Communication" },
  { href: "/setup/meetings", label: "Meetings", icon: Video, roles: ADMIN_ROLES, group: "Communication" },

  { href: "/teacher-dashboard", label: "Dashboard", icon: LayoutDashboard, roles: ["TEACHER"], group: "Main" },
  { href: "/profile", label: "My Profile", icon: UserRound, roles: ["TEACHER"], group: "Main" },
  { href: "/attendance", label: "Attendance", icon: CalendarCheck, roles: ["TEACHER"], group: "Academic" },
  { href: "/teacher-homework", label: "Homework", icon: ClipboardList, roles: ["TEACHER"], group: "Academic" },
  { href: "/teacher-courses", label: "LMS Courses", icon: BookOpen, roles: ["TEACHER"], group: "Academic" },
  { href: "/teacher-timetable", label: "Timetable", icon: CalendarCheck, roles: ["TEACHER"], group: "Academic" },
  { href: "/teacher-exams", label: "Exams & Marks", icon: GraduationCap, roles: ["TEACHER"], group: "Academic" },
  { href: "/teachers/curriculum", label: "Curriculum", icon: Album, roles: ["TEACHER"], group: "Academic" },
  { href: "/teachers/notice", label: "Notices", icon: NotebookIcon, roles: ["TEACHER"], group: "Communication" },
  { href: "/teachers/meetings", label: "Meetings", icon: Video, roles: ["TEACHER"], group: "Communication" },
  { href: "/library", label: "Library", icon: Library, roles: ["TEACHER"], group: "Resources" },

  { href: "/student-dashboard", label: "Dashboard", icon: LayoutDashboard, roles: ["STUDENT"], group: "Main" },
  { href: "/profile", label: "My Profile", icon: UserRound, roles: ["STUDENT"], group: "Main" },
  { href: "/attendance/my", label: "My Attendance", icon: CalendarCheck, roles: ["STUDENT"], group: "Academic" },
  { href: "/student-homework", label: "Homework", icon: ClipboardList, roles: ["STUDENT"], group: "Academic" },
  { href: "/student-courses", label: "My Courses", icon: BookOpen, roles: ["STUDENT"], group: "Academic" },
  { href: "/student-timetable", label: "Timetable", icon: CalendarCheck, roles: ["STUDENT"], group: "Academic" },
  { href: "/student-exams", label: "Report Cards", icon: GraduationCap, roles: ["STUDENT"], group: "Academic" },
  { href: "/students/notice", label: "Notices", icon: NotebookIcon, roles: ["STUDENT"], group: "Communication" },
  { href: "/students/meetings", label: "Meetings", icon: Video, roles: ["STUDENT"], group: "Communication" },
  { href: "/fees", label: "Fees", icon: CreditCard, roles: ["STUDENT"], group: "Finance" },
  { href: "/library", label: "Library", icon: Library, roles: ["STUDENT"], group: "Resources" },

  { href: "/parent-dashboard", label: "Dashboard", icon: LayoutDashboard, roles: ["PARENT"], group: "Main" },
  { href: "/profile", label: "My Profile", icon: UserRound, roles: ["PARENT"], group: "Main" },
  { href: "/parent-homework", label: "Homework", icon: ClipboardList, roles: ["PARENT"], group: "Academic" },
  { href: "/parent-courses", label: "Child Courses", icon: BookOpen, roles: ["PARENT"], group: "Academic" },
  { href: "/parent-timetable", label: "Timetable", icon: CalendarCheck, roles: ["PARENT"], group: "Academic" },
  { href: "/parent-exams", label: "Child Results", icon: GraduationCap, roles: ["PARENT"], group: "Academic" },
  { href: "/parents/notice", label: "Notices", icon: NotebookIcon, roles: ["PARENT"], group: "Communication" },
  { href: "/attendance/my", label: "Child Attendance", icon: CalendarCheck, roles: ["PARENT"], group: "Academic" },
  { href: "/fees", label: "Child Fees", icon: CreditCard, roles: ["PARENT"], group: "Finance" },
  {
    href: "/communication",
    label: "Communication",
    icon: Presentation,
    roles: [...ADMIN_ROLES, "TEACHER", "STUDENT", "PARENT"],
    group: "Communication",
  },
];

function formatRole(value: string) {
  return value
    .toLowerCase()
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function getRoleGradient(role: string): string {
  const map: Record<string, string> = {
    STUDENT: "linear-gradient(135deg,#7c3aed,#6d28d9)",
    TEACHER: "linear-gradient(135deg,#059669,#047857)",
    PARENT: "linear-gradient(135deg,#2563eb,#1d4ed8)",
    SUPER_ADMIN: "linear-gradient(135deg,#e11d48,#be123c)",
    SCHOOL_OWNER: "linear-gradient(135deg,#d97706,#b45309)",
    SCHOOL_ADMIN: "linear-gradient(135deg,#475569,#334155)",
  };
  return map[role] ?? "linear-gradient(135deg,#475569,#334155)";
}

function getInitials(name: string): string {
  return name
    .split(" ")
    .slice(0, 2)
    .map((n) => n[0])
    .join("")
    .toUpperCase();
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [auth, setAuth] = useState<AuthResponse | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [desktopOpen, setDesktopOpen] = useState(true);

  useEffect(() => {
    const saved = getSavedAuth();
    if (!saved) { router.replace("/login"); return; }
    if (saved.user.must_change_password && pathname !== "/change-password") {
      router.replace("/change-password"); return;
    }
    const protectedPaths = new Set(navItems.map((item) => item.href));
    if (protectedPaths.has(pathname)) {
      const canOpen = navItems.some((item) => item.href === pathname && item.roles.includes(saved.user.role));
      if (!canOpen) { router.replace(dashboardPathForRole(saved.user.role, Boolean(saved.user.must_change_password))); return; }
    }
    setAuth(saved);
  }, [pathname, router]);

  const visibleNav = useMemo(() => {
    if (!auth) return [];
    return navItems.filter((item) => item.roles.includes(auth.user.role));
  }, [auth]);

  const groupedNav = useMemo(() => {
    const groups: Record<string, NavItem[]> = {};
    visibleNav.forEach((item) => {
      const g = item.group ?? "Other";
      if (!groups[g]) groups[g] = [];
      groups[g].push(item);
    });
    return groups;
  }, [visibleNav]);

  const logout = () => { clearAuth(); router.replace("/login"); };

  if (!auth) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "#f1f5f9" }}>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
          <div style={{ width: 32, height: 32, border: "3px solid #e2e8f0", borderTopColor: "#7c3aed", borderRadius: "50%", animation: "spin 0.7s linear infinite" }} />
          <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
          <p style={{ fontSize: "0.875rem", color: "#94a3b8", margin: 0 }}>Loading…</p>
        </div>
      </div>
    );
  }

  const SIDEBAR_W = 264;
  const roleGradient = getRoleGradient(auth.user.role);
  const initials = getInitials(auth.user.full_name);

  return (
    <>
      <style>{`
        .as-sidebar {
          position: fixed;
          top: 0; left: 0; bottom: 0;
          width: ${SIDEBAR_W}px;
          background: #0f172a;
          border-right: 1px solid rgba(255,255,255,0.06);
          display: flex;
          flex-direction: column;
          z-index: 40;
          transition: transform 0.25s cubic-bezier(0.4,0,0.2,1);
          /* CRITICAL: allow inner flex children to shrink/scroll */
          overflow: hidden;
        }
        .as-sidebar-head {
          flex-shrink: 0;
          padding: 18px 14px 14px;
          border-bottom: 1px solid rgba(255,255,255,0.06);
        }
        .as-nav-scroll {
          /* This is the key: flex: 1 + min-height: 0 enables overflow-y scroll */
          flex: 1;
          min-height: 0;
          overflow-y: auto;
          padding: 10px 8px 6px;
          scrollbar-width: thin;
          scrollbar-color: #334155 transparent;
        }
        .as-nav-scroll::-webkit-scrollbar { width: 4px; }
        .as-nav-scroll::-webkit-scrollbar-thumb { background: #334155; border-radius: 99px; }
        .as-nav-scroll::-webkit-scrollbar-track { background: transparent; }
        .as-sidebar-foot {
          flex-shrink: 0;
          padding: 10px 8px 14px;
          border-top: 1px solid rgba(255,255,255,0.06);
        }
        .as-group-label {
          font-size: 0.6rem;
          font-weight: 800;
          letter-spacing: 0.1em;
          text-transform: uppercase;
          color: #334155;
          padding: 8px 10px 3px;
        }
        .as-group-label:first-child { padding-top: 2px; }
        .as-nav-link {
          display: flex;
          align-items: center;
          gap: 9px;
          padding: 7px 10px;
          border-radius: 9px;
          font-size: 0.8rem;
          font-weight: 500;
          color: #94a3b8;
          text-decoration: none;
          transition: background 0.13s, color 0.13s;
          position: relative;
          margin-bottom: 1px;
        }
        .as-nav-link:hover { background: rgba(255,255,255,0.06); color: #cbd5e1; }
        .as-nav-link.active {
          background: rgba(124,58,237,0.15);
          color: #c4b5fd;
        }
        .as-nav-link.active::before {
          content: '';
          position: absolute;
          left: 0; top: 20%; bottom: 20%;
          width: 3px;
          background: #7c3aed;
          border-radius: 0 3px 3px 0;
        }
        .as-header {
          position: sticky; top: 0; z-index: 20;
          height: 60px;
          background: rgba(255,255,255,0.93);
          backdrop-filter: blur(12px);
          border-bottom: 1px solid #e2e8f0;
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 0 20px;
          gap: 12px;
        }
        .as-icon-btn {
          width: 34px; height: 34px;
          border-radius: 8px;
          border: 1px solid #e2e8f0;
          background: transparent;
          color: #64748b;
          display: flex; align-items: center; justify-content: center;
          cursor: pointer;
          transition: background 0.13s;
          flex-shrink: 0;
        }
        .as-icon-btn:hover { background: #f1f5f9; }
        .as-logout-btn {
          display: inline-flex; align-items: center; gap: 5px;
          padding: 6px 13px;
          border-radius: 9px;
          border: 1px solid #e2e8f0;
          background: transparent;
          font-size: 0.8rem; font-weight: 600;
          color: #64748b;
          cursor: pointer;
          transition: background 0.13s, color 0.13s, border-color 0.13s;
          white-space: nowrap;
        }
        .as-logout-btn:hover { background: #fef2f2; color: #dc2626; border-color: #fecaca; }
        .as-avatar {
          width: 33px; height: 33px;
          border-radius: 50%;
          display: flex; align-items: center; justify-content: center;
          font-size: 0.7rem; font-weight: 800;
          color: white;
          flex-shrink: 0;
          letter-spacing: 0.02em;
        }
        .as-overlay {
          position: fixed; inset: 0; z-index: 30;
          background: rgba(15,23,42,0.45);
          border: none; cursor: pointer;
          width: 100%; height: 100%;
        }
        @media (max-width: 1023px) {
          .as-sidebar { transform: translateX(-100%); }
          .as-sidebar.open { transform: translateX(0); }
          .as-desktop-toggle { display: none !important; }
          .as-main { padding-left: 0 !important; }
        }
        @media (min-width: 1024px) {
          .as-mobile-toggle { display: none !important; }
          .as-overlay { display: none !important; }
        }
      `}</style>

      <div style={{ minHeight: "100vh", background: "#f1f5f9" }}>

        {/* ── Sidebar ── */}
        <aside className={`as-sidebar${mobileOpen ? " open" : ""}${!desktopOpen ? " lg-hidden" : ""}`}
          style={!desktopOpen ? { transform: "translateX(-100%)" } : {}}>

          {/* Head */}
          <div className="as-sidebar-head">
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <button
                type="button"
                onClick={() => router.replace(dashboardPathForRole(auth.user.role, Boolean(auth.user.must_change_password)))}
                style={{ background: "none", border: "none", cursor: "pointer", padding: 0, textAlign: "left", minWidth: 0 }}
              >
                <p style={{ fontSize: "0.55rem", fontWeight: 800, letterSpacing: "0.12em", textTransform: "uppercase", color: "#7c3aed", margin: "0 0 3px" }}>
                  ERP Portal
                </p>
                <h1 style={{ fontSize: "0.9rem", fontWeight: 700, color: "#f1f5f9", margin: 0, maxWidth: 190, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {auth.school?.name || "School ERP"}
                </h1>
                {auth.school?.school_code && (
                  <p style={{ fontSize: "0.65rem", color: "#475569", margin: "2px 0 0" }}>#{auth.school.school_code}</p>
                )}
              </button>
              
            </div>
          </div>

          {/* Scrollable nav — flex:1 + min-height:0 is the fix */}
          <nav className="as-nav-scroll">
            {Object.entries(groupedNav).map(([group, items]) => (
              <div key={group}>
                <div className="as-group-label">{group}</div>
                {items.map((item, i) => {
                  const Icon = item.icon;
                  const active = pathname === item.href;
                  return (
                    <Link
                      key={`${item.href}-${i}`}
                      href={item.href}
                      onClick={() => setMobileOpen(false)}
                      className={`as-nav-link${active ? " active" : ""}`}
                    >
                      <Icon size={15} style={{ flexShrink: 0, opacity: active ? 1 : 0.65 }} />
                      <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1 }}>{item.label}</span>
                      {active && <ChevronRight size={11} style={{ opacity: 0.5, flexShrink: 0 }} />}
                    </Link>
                  );
                })}
              </div>
            ))}
          </nav>

          {/* Footer user card */}
          <div className="as-sidebar-foot">
            <div style={{ display: "flex", alignItems: "center", gap: 9, padding: "9px 10px", borderRadius: 10, background: "rgba(255,255,255,0.04)" }}>
              <div className="as-avatar" style={{ background: roleGradient }}>{initials}</div>
              <div style={{ minWidth: 0, flex: 1 }}>
                <p style={{ fontSize: "0.78rem", fontWeight: 600, color: "#e2e8f0", margin: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {auth.user.full_name}
                </p>
                <p style={{ fontSize: "0.65rem", color: "#475569", margin: "1px 0 0" }}>{formatRole(auth.user.role)}</p>
              </div>
              <button onClick={logout} title="Logout"
                style={{ background: "none", border: "none", cursor: "pointer", color: "#475569", padding: 4, borderRadius: 6, display: "flex", alignItems: "center", transition: "color 0.13s" }}>
                <LogOut size={14} />
              </button>
            </div>
          </div>
        </aside>

        {/* Mobile overlay */}
        {mobileOpen && <button className="as-overlay" onClick={() => setMobileOpen(false)} aria-label="Close menu" />}

        {/* ── Main ── */}
        <div
          className="as-main"
          style={{ paddingLeft: desktopOpen ? SIDEBAR_W : 0, transition: "padding-left 0.25s cubic-bezier(0.4,0,0.2,1)" }}
        >
          {/* Top header */}
          <header className="as-header">
            <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
              <button className="as-icon-btn as-mobile-toggle" onClick={() => setMobileOpen(true)} aria-label="Open sidebar">
                <Menu size={17} />
              </button>
              <button className="as-icon-btn as-desktop-toggle" onClick={() => setDesktopOpen((v) => !v)} aria-label="Toggle sidebar">
                <Menu size={17} />
              </button>
              <div style={{ display: "none" }} className="md-show">
                <button
                  type="button"
                  onClick={() => router.replace(dashboardPathForRole(auth.user.role, Boolean(auth.user.must_change_password)))}
                  style={{ background: "none", border: "none", cursor: "pointer", padding: 0, textAlign: "left" }}
                >
                  <p style={{ fontSize: "0.875rem", fontWeight: 600, color: "#0f172a", margin: 0 }}>{auth.user.full_name}</p>
                  <p style={{ fontSize: "0.72rem", color: "#94a3b8", margin: 0 }}>{formatRole(auth.user.role)} · {auth.user.login_id}</p>
                </button>
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <div className="as-avatar" style={{ background: roleGradient, width: 30, height: 30, fontSize: "0.65rem" }}>{initials}</div>
              <button className="as-logout-btn" onClick={logout}>
                <LogOut size={13} /> Logout
              </button>
            </div>
          </header>

          <main style={{ padding: "24px 20px", minHeight: "calc(100vh - 60px)" }}>
            {children}
          </main>
        </div>
      </div>
    </>
  );
}

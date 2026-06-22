"use client";

import { useEffect, useState } from "react";
import {
  AlertTriangle, BookOpen, CheckCircle2, ChevronDown, ChevronUp,
  Download, FileText, Loader2, RefreshCw, Users, UserRound,
  ClipboardList, GraduationCap, TrendingUp, Library,
} from "lucide-react";

import AppShell from "@/components/AppShell";
import { Button, Card, Input, Label } from "@/components/ui";
import { ACADEMIC_SESSION_CHANGED_EVENT, apiFetch, fileUrl, getSelectedAcademicSessionId, setSelectedAcademicSessionId } from "@/lib/api";
import type { AcademicClass, AcademicSession, Section } from "@/types";

// ── Types ──────────────────────────────────────────────────────────────────
type Overview = {
  total_students: number; active_students: number;
  total_teachers: number; active_teachers: number;
  total_classes: number; total_exams: number; published_exams: number;
  total_homework: number; avg_attendance_pct: number;
  low_attendance_students: number; library_books: number;
  library_issued: number; overdue_books: number;
};

type AttRow = {
  student_id: number; student_name: string; admission_no: string;
  roll_number?: string | null; class_name?: string | null; section_name?: string | null;
  total_days: number; present: number; absent: number; leave: number; half_day: number;
  percentage: number; low_attendance: boolean;
};
type AttReport = {
  session_name: string; total_students: number;
  avg_percentage: number; low_attendance_count: number; rows: AttRow[];
};

type StudentRow = {
  photo_url: any;
  student_id: number; admission_no: string; roll_number?: string | null;
  full_name: string; gender?: string | null; class_name?: string | null;
  section_name?: string | null; guardian_name?: string | null;
  guardian_phone?: string | null; admission_date?: string | null; status: string;
};
type StudentReport = {
  total_students: number; active_students: number;
  class_breakdown: { class: string; count: number }[];
  rows: StudentRow[];
};

type TeacherRow = {
  teacher_id: number; employee_id: string; full_name: string;
  photo_url?: string | null;
  department_name?: string | null; email?: string | null; phone?: string | null;
  qualification?: string | null; joining_date?: string | null;
  status: string; subjects_assigned: number; classes_assigned: number;
};
type TeacherReport = {
  total_teachers: number; active_teachers: number;
  department_breakdown: { department: string; count: number }[];
  rows: TeacherRow[];
};

type HwRow = {
  assignment_id: number; title: string; subject_name?: string | null;
  class_name?: string | null; section_name?: string | null; due_date: string;
  teacher_name?: string | null; total_students: number; submitted: number;
  checked: number; pending: number; submission_rate: number;
};
type HwReport = { rows: HwRow[] };

// ── Helpers ────────────────────────────────────────────────────────────────
type ReportTab = "overview" | "students" | "attendance" | "teachers" | "homework";

function fmt(d: string) {
  return new Date(d).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

function exportCSV(rows: Record<string, unknown>[], filename: string) {
  if (!rows.length) return;
  const headers = Object.keys(rows[0]);
  const csv = [
    headers.join(","),
    ...rows.map((r) =>
      headers.map((h) => {
        const v = String(r[h] ?? "");
        return v.includes(",") ? `"${v}"` : v;
      }).join(",")
    ),
  ].join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

// ── Stat Card ────────────────────────────────────────────────────────────────
function StatCard({ label, value, sub, color, icon: Icon }: {
  label: string; value: string | number; sub?: string;
  color?: string; icon?: React.ElementType;
}) {
  return (
    <Card>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs text-slate-500">{label}</p>
          <p className={`mt-1 text-2xl font-bold ${color ?? "text-slate-900"}`}>{value}</p>
          {sub && <p className="mt-0.5 text-xs text-slate-400">{sub}</p>}
        </div>
        {Icon && <Icon size={22} className="text-slate-200 mt-1" />}
      </div>
    </Card>
  );
}

// ── Sortable table header ────────────────────────────────────────────────────
function TH({ label, col, sort, onSort }: {
  label: string; col: string;
  sort: { col: string; dir: "asc" | "desc" };
  onSort: (col: string) => void;
}) {
  const active = sort.col === col;
  return (
    <th
      className="cursor-pointer select-none px-4 py-3 text-left text-xs font-medium text-slate-500 hover:text-slate-700"
      onClick={() => onSort(col)}
    >
      <span className="flex items-center gap-1">
        {label}
        {active ? (sort.dir === "asc" ? <ChevronUp size={12} /> : <ChevronDown size={12} />) : null}
      </span>
    </th>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// MAIN PAGE
// ══════════════════════════════════════════════════════════════════════════════
export default function ReportsPage() {
  const [tab, setTab] = useState<ReportTab>("overview");

  // shared filters
  const [sessions, setSessions] = useState<AcademicSession[]>([]);
  const [classes, setClasses] = useState<AcademicClass[]>([]);
  const [sections, setSections] = useState<Section[]>([]);
  const [sessionId, setSessionId] = useState("");
  const [classId, setClassId] = useState("");
  const [sectionId, setSectionId] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [includeInactive, setIncludeInactive] = useState(false);

  // data
  const [overview, setOverview] = useState<Overview | null>(null);
  const [attReport, setAttReport] = useState<AttReport | null>(null);
  const [stuReport, setStuReport] = useState<StudentReport | null>(null);
  const [tchReport, setTchReport] = useState<TeacherReport | null>(null);
  const [hwReport, setHwReport] = useState<HwReport | null>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // sort state per tab
  const [attSort, setAttSort] = useState<{ col: string; dir: "asc" | "desc" }>({ col: "student_name", dir: "asc" });
  const [stuSort, setStuSort] = useState<{ col: string; dir: "asc" | "desc" }>({ col: "full_name", dir: "asc" });
  const [tchSort, setTchSort] = useState<{ col: string; dir: "asc" | "desc" }>({ col: "full_name", dir: "asc" });

  const err = (e: unknown) => setError(e instanceof Error ? e.message : "Failed to load report");

  useEffect(() => {
    Promise.all([
      apiFetch<AcademicSession[]>("/academic-sessions"),
      apiFetch<AcademicClass[]>("/classes"),
      apiFetch<Section[]>("/sections"),
    ]).then(([s, c, sec]) => {
      setSessions(s); setClasses(c); setSections(sec);
      const selected = getSelectedAcademicSessionId();
      const active = s.find((x) => x.is_active);
      const validSelected = selected && s.some((x) => String(x.id) === selected) ? selected : "";
      const nextSessionId = validSelected || (active ? String(active.id) : "");
      if (nextSessionId) {
        setSessionId(nextSessionId);
        setSelectedAcademicSessionId(nextSessionId);
      }
    }).catch(() => {});
    loadOverview();
  }, []);

  useEffect(() => {
    const onSessionChange = () => {
      const selected = getSelectedAcademicSessionId();
      if (selected) setSessionId(selected);
      setClassId("");
      setSectionId("");
    };
    window.addEventListener(ACADEMIC_SESSION_CHANGED_EVENT, onSessionChange);
    return () => window.removeEventListener(ACADEMIC_SESSION_CHANGED_EVENT, onSessionChange);
  }, []);


  useEffect(() => {
    if (!sessionId) return;
    Promise.all([
      apiFetch<AcademicClass[]>("/classes"),
      apiFetch<Section[]>("/sections"),
    ]).then(([c, sec]) => {
      setClasses(c);
      setSections(sec);
      setClassId("");
      setSectionId("");
    }).catch(() => {});
  }, [sessionId]);

  useEffect(() => {
    if (tab === "overview") loadOverview();
    else if (tab === "attendance" && sessionId) loadAtt();
    else if (tab === "students") loadStudents();
    else if (tab === "teachers") loadTeachers();
    else if (tab === "homework") loadHomework();
  }, [tab, sessionId]);

  const loadOverview = async () => {
    setLoading(true); setError("");
    try { setOverview(await apiFetch<Overview>("/reports/overview")); }
    catch (e) { err(e); } finally { setLoading(false); }
  };

  const loadAtt = async () => {
    if (!sessionId) { setError("Select a session"); return; }
    setLoading(true); setError("");
    try {
      const p = new URLSearchParams({ session_id: sessionId });
      if (classId) p.set("class_id", classId);
      if (sectionId) p.set("section_id", sectionId);
      if (dateFrom) p.set("date_from", dateFrom);
      if (dateTo) p.set("date_to", dateTo);
      setAttReport(await apiFetch<AttReport>(`/reports/attendance?${p}`));
    } catch (e) { err(e); } finally { setLoading(false); }
  };

  const loadStudents = async () => {
    setLoading(true); setError("");
    try {
      const p = new URLSearchParams();
      if (classId) p.set("class_id", classId);
      if (sectionId) p.set("section_id", sectionId);
      if (includeInactive) p.set("include_inactive", "true");
      setStuReport(await apiFetch<StudentReport>(`/reports/students?${p}`));
    } catch (e) { err(e); } finally { setLoading(false); }
  };

  const loadTeachers = async () => {
    setLoading(true); setError("");
    try {
      const p = new URLSearchParams();
      if (includeInactive) p.set("include_inactive", "true");
      setTchReport(await apiFetch<TeacherReport>(`/reports/teachers?${p}`));
    } catch (e) { err(e); } finally { setLoading(false); }
  };

  const loadHomework = async () => {
    setLoading(true); setError("");
    try {
      const p = new URLSearchParams();
      if (sessionId) p.set("session_id", sessionId);
      if (classId) p.set("class_id", classId);
      setHwReport(await apiFetch<HwReport>(`/reports/homework?${p}`));
    } catch (e) { err(e); } finally { setLoading(false); }
  };

  const handleLoad = () => {
    if (tab === "overview") loadOverview();
    else if (tab === "attendance") loadAtt();
    else if (tab === "students") loadStudents();
    else if (tab === "teachers") loadTeachers();
    else if (tab === "homework") loadHomework();
  };

  const sortRows = <T extends Record<string, unknown>>(
    rows: T[], sort: { col: string; dir: "asc" | "desc" }
  ): T[] => {
    return [...rows].sort((a, b) => {
      const av = a[sort.col] ?? ""; const bv = b[sort.col] ?? "";
      const cmp = String(av).localeCompare(String(bv), undefined, { numeric: true });
      return sort.dir === "asc" ? cmp : -cmp;
    });
  };

  const toggleSort = (
    col: string,
    current: { col: string; dir: "asc" | "desc" },
    set: (s: { col: string; dir: "asc" | "desc" }) => void
  ) => {
    set({ col, dir: current.col === col && current.dir === "asc" ? "desc" : "asc" });
  };

  const tabs: { key: ReportTab; label: string; icon: React.ElementType }[] = [
    { key: "overview",    label: "Overview",    icon: TrendingUp },
    { key: "students",    label: "Students",    icon: Users },
    { key: "attendance",  label: "Attendance",  icon: CheckCircle2 },
    { key: "teachers",    label: "Teachers",    icon: UserRound },
    { key: "homework",    label: "Homework",    icon: ClipboardList },
  ];

  const filteredSections = sections.filter((s) => !classId || s.class_id === Number(classId));

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-start justify-between flex-wrap gap-3">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Reports</h1>
            <p className="mt-1 text-sm text-slate-500">School-wide data reports and analytics</p>
          </div>
          <div className="flex gap-2">
            <Button onClick={handleLoad} className="flex items-center gap-2">
              <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
              {loading ? "Loading…" : "Load Report"}
            </Button>
          </div>
        </div>

        {error && (
          <div className="flex items-center gap-2 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700 border border-red-200">
            <AlertTriangle size={15} /> {error}
          </div>
        )}

        {/* Filters */}
        {tab !== "overview" && (
          <Card>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-6">
              {(tab === "attendance" || tab === "homework") && (
                <div>
                  <Label>Session</Label>
                  <select className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-slate-400"
                    value={sessionId} onChange={(e) => { setSessionId(e.target.value); setSelectedAcademicSessionId(e.target.value || null); }}>
                    <option value="">All sessions</option>
                    {sessions.map((s) => <option key={s.id} value={s.id}>{s.name}{s.is_active ? " ✓" : ""}</option>)}
                  </select>
                </div>
              )}
              {(tab === "students" || tab === "attendance" || tab === "homework") && (
                <div>
                  <Label>Class</Label>
                  <select className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-slate-400"
                    value={classId} onChange={(e) => { setClassId(e.target.value); setSectionId(""); }}>
                    <option value="">All classes</option>
                    {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                </div>
              )}
              {(tab === "students" || tab === "attendance") && classId && (
                <div>
                  <Label>Section</Label>
                  <select className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-slate-400"
                    value={sectionId} onChange={(e) => setSectionId(e.target.value)}>
                    <option value="">All sections</option>
                    {filteredSections.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                  </select>
                </div>
              )}
              {tab === "attendance" && (
                <>
                  <div><Label>From date</Label><Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} /></div>
                  <div><Label>To date</Label><Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} /></div>
                </>
              )}
              {(tab === "students" || tab === "teachers") && (
                <div className="flex items-end">
                  <label className="flex cursor-pointer items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm w-full">
                    <input type="checkbox" checked={includeInactive} onChange={(e) => setIncludeInactive(e.target.checked)} />
                    Include inactive
                  </label>
                </div>
              )}
            </div>
          </Card>
        )}

        {/* Tabs */}
        <div className="flex gap-1 border-b border-slate-200 overflow-x-auto">
          {tabs.map((t) => {
            const Icon = t.icon;
            return (
              <button key={t.key} onClick={() => setTab(t.key)}
                className={`flex items-center gap-1.5 px-4 py-2 text-sm font-medium transition border-b-2 -mb-px whitespace-nowrap ${
                  tab === t.key ? "border-slate-900 text-slate-900" : "border-transparent text-slate-500 hover:text-slate-700"
                }`}>
                <Icon size={14} /> {t.label}
              </button>
            );
          })}
        </div>

        {/* ── OVERVIEW ──────────────────────────────────────────────────── */}
        {tab === "overview" && (
          <div className="space-y-6">
            {loading && !overview && (
              <div className="flex justify-center py-12"><Loader2 className="animate-spin text-slate-400" /></div>
            )}
            {overview && (
              <>
                <div>
                  <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-400">People</p>
                  <div className="grid gap-4 grid-cols-2 sm:grid-cols-4">
                    <StatCard label="Total Students" value={overview.total_students} sub={`${overview.active_students} active`} icon={Users} />
                    <StatCard label="Total Teachers" value={overview.total_teachers} sub={`${overview.active_teachers} active`} icon={UserRound} />
                    <StatCard label="Classes" value={overview.total_classes} icon={GraduationCap} />
                    <StatCard label="Avg Attendance" value={`${overview.avg_attendance_pct}%`}
                      sub={`${overview.low_attendance_students} below 75%`}
                      color={overview.avg_attendance_pct < 75 ? "text-amber-600" : "text-emerald-600"} icon={CheckCircle2} />
                  </div>
                </div>
                <div>
                  <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-400">Academics</p>
                  <div className="grid gap-4 grid-cols-2 sm:grid-cols-4">
                    <StatCard label="Total Exams" value={overview.total_exams} sub={`${overview.published_exams} published`} icon={GraduationCap} />
                    <StatCard label="Homework Assignments" value={overview.total_homework} icon={ClipboardList} />
                    <StatCard label="Library Books" value={overview.library_books} sub={`${overview.library_issued} issued`} icon={Library} />
                    <StatCard label="Overdue Books" value={overview.overdue_books}
                      color={overview.overdue_books > 0 ? "text-red-600" : "text-emerald-600"}
                      sub={overview.overdue_books > 0 ? "Follow up required" : "All returned on time"} icon={BookOpen} />
                  </div>
                </div>

                {/* Low attendance alert */}
                {overview.low_attendance_students > 0 && (
                  <div className="flex items-center gap-2 rounded-xl bg-amber-50 border border-amber-200 px-4 py-3 text-sm text-amber-800">
                    <AlertTriangle size={16} />
                    <strong>{overview.low_attendance_students}</strong> student{overview.low_attendance_students > 1 ? "s" : ""} have attendance below 75% in the current session.
                    <button onClick={() => setTab("attendance")} className="ml-auto text-amber-700 underline text-xs">View report →</button>
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* ── STUDENTS REPORT ────────────────────────────────────────────── */}
        {tab === "students" && (
          <div className="space-y-4">
            {loading && <div className="flex justify-center py-12"><Loader2 className="animate-spin text-slate-400" /></div>}
            {stuReport && !loading && (
              <>
                <div className="grid gap-4 grid-cols-2 sm:grid-cols-4">
                  <StatCard label="Total Students" value={stuReport.total_students} />
                  <StatCard label="Active Students" value={stuReport.active_students} color="text-emerald-600" />
                  <StatCard label="Showing" value={stuReport.rows.length} />
                  <div className="flex items-center justify-end">
                    <button onClick={() => exportCSV(stuReport.rows as unknown as Record<string, unknown>[], "student_report.csv")}
                      className="flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm hover:bg-slate-50">
                      <Download size={14} /> Export CSV
                    </button>
                  </div>
                </div>

                {stuReport.class_breakdown.length > 0 && (
                  <Card>
                    <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-400">Class Distribution</p>
                    <div className="flex flex-wrap gap-2">
                      {stuReport.class_breakdown.map((b) => (
                        <div key={b.class} className="rounded-xl bg-slate-100 px-3 py-1.5 text-sm">
                          <span className="font-medium text-slate-800">{b.class}</span>
                          <span className="ml-1.5 text-slate-500">{b.count}</span>
                        </div>
                      ))}
                    </div>
                  </Card>
                )}

                <Card className="overflow-hidden p-0">
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-slate-100 bg-slate-50">
                          {[
                            ["full_name","Name"],["admission_no","Adm No"],["class_name","Class"],
                            ["section_name","Section"],["gender","Gender"],
                            ["guardian_name","Guardian"],["guardian_phone","Guardian Phone"],
                            ["admission_date","Admission"],["status","Status"],
                          ].map(([col, label]) => (
                            <TH key={col} col={col} label={label} sort={stuSort} onSort={(c) => toggleSort(c, stuSort, setStuSort)} />
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {sortRows(stuReport.rows as unknown as Record<string, unknown>[], stuSort).map((row) => {
                          const r = row as unknown as StudentRow;
                          return (
                            <tr key={r.student_id} className="hover:bg-slate-50 transition">
                              <td className="px-4 py-2.5 font-medium text-slate-900">
                                <div className="flex items-center gap-3">
                                  <div className="flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-full bg-slate-100 text-slate-400">
                                    {r.photo_url ? (
                                      // eslint-disable-next-line @next/next/no-img-element
                                      <img src={fileUrl(r.photo_url)} alt={r.full_name} className="h-full w-full object-cover" />
                                    ) : (
                                      <UserRound size={17} />
                                    )}
                                  </div>
                                  <span>{r.full_name}</span>
                                </div>
                              </td>
                              <td className="px-4 py-2.5 font-mono text-xs text-slate-500">{r.admission_no}</td>
                              <td className="px-4 py-2.5 text-slate-600">{r.class_name ?? "—"}</td>
                              <td className="px-4 py-2.5 text-slate-600">{r.section_name ?? "—"}</td>
                              <td className="px-4 py-2.5 text-slate-500 capitalize">{r.gender?.toLowerCase() ?? "—"}</td>
                              <td className="px-4 py-2.5 text-slate-600">{r.guardian_name ?? "—"}</td>
                              <td className="px-4 py-2.5 text-slate-500">{r.guardian_phone ?? "—"}</td>
                              <td className="px-4 py-2.5 text-slate-500 text-xs">{r.admission_date ? fmt(r.admission_date) : "—"}</td>
                              <td className="px-4 py-2.5">
                                <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                                  r.status === "ACTIVE" ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-600"
                                }`}>{r.status}</span>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </Card>
              </>
            )}
            {!stuReport && !loading && (
              <Card><p className="py-8 text-center text-sm text-slate-400">Click "Load Report" to generate the student report.</p></Card>
            )}
          </div>
        )}

        {/* ── ATTENDANCE REPORT ──────────────────────────────────────────── */}
        {tab === "attendance" && (
          <div className="space-y-4">
            {loading && <div className="flex justify-center py-12"><Loader2 className="animate-spin text-slate-400" /></div>}
            {attReport && !loading && (
              <>
                <div className="grid gap-4 grid-cols-2 sm:grid-cols-4">
                  <StatCard label="Students" value={attReport.total_students} />
                  <StatCard label="Avg Attendance" value={`${attReport.avg_percentage}%`}
                    color={attReport.avg_percentage < 75 ? "text-amber-600" : "text-emerald-600"} />
                  <StatCard label="Below 75%" value={attReport.low_attendance_count}
                    color={attReport.low_attendance_count > 0 ? "text-red-600" : "text-emerald-600"} />
                  <div className="flex items-center justify-end">
                    <button onClick={() => exportCSV(attReport.rows as unknown as Record<string, unknown>[], "attendance_report.csv")}
                      className="flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm hover:bg-slate-50">
                      <Download size={14} /> Export CSV
                    </button>
                  </div>
                </div>

                {attReport.low_attendance_count > 0 && (
                  <div className="flex items-center gap-2 rounded-xl bg-amber-50 border border-amber-200 px-4 py-3 text-sm text-amber-800">
                    <AlertTriangle size={15} />
                    <strong>{attReport.low_attendance_count}</strong> student{attReport.low_attendance_count > 1 ? "s" : ""} below 75% attendance — highlighted in the table below.
                  </div>
                )}

                <Card className="overflow-hidden p-0">
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-slate-100 bg-slate-50">
                          {[
                            ["student_name","Name"],["admission_no","Adm No"],
                            ["class_name","Class"],["section_name","Section"],
                            ["total_days","Total"],["present","Present"],
                            ["absent","Absent"],["leave","Leave"],["half_day","Half Day"],["percentage","Att %"],
                          ].map(([col, label]) => (
                            <TH key={col} col={col} label={label} sort={attSort} onSort={(c) => toggleSort(c, attSort, setAttSort)} />
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {sortRows(attReport.rows as unknown as Record<string, unknown>[], attSort).map((row) => {
                          const r = row as unknown as AttRow;
                          return (
                            <tr key={r.student_id} className={`transition ${r.low_attendance ? "bg-amber-50" : "hover:bg-slate-50"}`}>
                              <td className="px-4 py-2.5 font-medium text-slate-900">
                                <div className="flex items-center gap-1.5">
                                  {r.low_attendance && <AlertTriangle size={12} className="text-amber-500 shrink-0" />}
                                  {r.student_name}
                                </div>
                              </td>
                              <td className="px-4 py-2.5 font-mono text-xs text-slate-500">{r.admission_no}</td>
                              <td className="px-4 py-2.5 text-slate-600">{r.class_name ?? "—"}</td>
                              <td className="px-4 py-2.5 text-slate-600">{r.section_name ?? "—"}</td>
                              <td className="px-4 py-2.5 text-center text-slate-600">{r.total_days}</td>
                              <td className="px-4 py-2.5 text-center font-medium text-emerald-600">{r.present}</td>
                              <td className="px-4 py-2.5 text-center font-medium text-red-500">{r.absent}</td>
                              <td className="px-4 py-2.5 text-center font-medium text-amber-500">{r.leave}</td>
                              <td className="px-4 py-2.5 text-center font-medium text-blue-500">{r.half_day}</td>
                              <td className="px-4 py-2.5 text-center">
                                <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                                  r.low_attendance ? "bg-amber-100 text-amber-700"
                                  : r.percentage >= 90 ? "bg-emerald-100 text-emerald-700"
                                  : "bg-slate-100 text-slate-600"
                                }`}>{r.percentage}%</span>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </Card>
              </>
            )}
            {!attReport && !loading && (
              <Card><p className="py-8 text-center text-sm text-slate-400">Select a session and click "Load Report".</p></Card>
            )}
          </div>
        )}

        {/* ── TEACHER REPORT ─────────────────────────────────────────────── */}
        {tab === "teachers" && (
          <div className="space-y-4">
            {loading && <div className="flex justify-center py-12"><Loader2 className="animate-spin text-slate-400" /></div>}
            {tchReport && !loading && (
              <>
                <div className="grid gap-4 grid-cols-2 sm:grid-cols-4">
                  <StatCard label="Total Teachers" value={tchReport.total_teachers} />
                  <StatCard label="Active" value={tchReport.active_teachers} color="text-emerald-600" />
                  <StatCard label="Departments" value={tchReport.department_breakdown.length} />
                  <div className="flex items-center justify-end">
                    <button onClick={() => exportCSV(tchReport.rows as unknown as Record<string, unknown>[], "teacher_report.csv")}
                      className="flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm hover:bg-slate-50">
                      <Download size={14} /> Export CSV
                    </button>
                  </div>
                </div>

                {tchReport.department_breakdown.length > 0 && (
                  <Card>
                    <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-400">Department Distribution</p>
                    <div className="flex flex-wrap gap-2">
                      {tchReport.department_breakdown.map((b) => (
                        <div key={b.department} className="rounded-xl bg-slate-100 px-3 py-1.5 text-sm">
                          <span className="font-medium text-slate-800">{b.department}</span>
                          <span className="ml-1.5 text-slate-500">{b.count}</span>
                        </div>
                      ))}
                    </div>
                  </Card>
                )}

                <Card className="overflow-hidden p-0">
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-slate-100 bg-slate-50">
                          {[
                            ["full_name","Name"],["employee_id","Emp ID"],["department_name","Department"],
                            ["email","Email"],["phone","Phone"],["qualification","Qualification"],
                            ["joining_date","Joining"],["subjects_assigned","Subjects"],
                            ["classes_assigned","Class Teacher"],["status","Status"],
                          ].map(([col, label]) => (
                            <TH key={col} col={col} label={label} sort={tchSort} onSort={(c) => toggleSort(c, tchSort, setTchSort)} />
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {sortRows(tchReport.rows as unknown as Record<string, unknown>[], tchSort).map((row) => {
                          const r = row as unknown as TeacherRow;
                          return (
                            <tr key={r.teacher_id} className="hover:bg-slate-50 transition">
                              <td className="px-4 py-2.5 font-medium text-slate-900">
                                <div className="flex items-center gap-3">
                                  <div className="flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-full bg-slate-100 text-slate-400">
                                    {r.photo_url ? (
                                      // eslint-disable-next-line @next/next/no-img-element
                                      <img src={fileUrl(r.photo_url)} alt={r.full_name} className="h-full w-full object-cover" />
                                    ) : (
                                      <UserRound size={17} />
                                    )}
                                  </div>
                                  <span>{r.full_name}</span>
                                </div>
                              </td>
                              <td className="px-4 py-2.5 font-mono text-xs text-slate-500">{r.employee_id}</td>
                              <td className="px-4 py-2.5 text-slate-600">{r.department_name ?? "—"}</td>
                              <td className="px-4 py-2.5 text-slate-500 text-xs">{r.email ?? "—"}</td>
                              <td className="px-4 py-2.5 text-slate-500">{r.phone ?? "—"}</td>
                              <td className="px-4 py-2.5 text-slate-500">{r.qualification ?? "—"}</td>
                              <td className="px-4 py-2.5 text-slate-500 text-xs">{r.joining_date ? fmt(r.joining_date) : "—"}</td>
                              <td className="px-4 py-2.5 text-center text-slate-600">{r.subjects_assigned}</td>
                              <td className="px-4 py-2.5 text-center text-slate-600">{r.classes_assigned}</td>
                              <td className="px-4 py-2.5">
                                <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                                  r.status === "ACTIVE" ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-600"
                                }`}>{r.status}</span>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </Card>
              </>
            )}
            {!tchReport && !loading && (
              <Card><p className="py-8 text-center text-sm text-slate-400">Click "Load Report" to generate the teacher report.</p></Card>
            )}
          </div>
        )}

        {/* ── HOMEWORK REPORT ────────────────────────────────────────────── */}
        {tab === "homework" && (
          <div className="space-y-4">
            {loading && <div className="flex justify-center py-12"><Loader2 className="animate-spin text-slate-400" /></div>}
            {hwReport && !loading && (
              <>
                <div className="flex justify-end">
                  <button onClick={() => exportCSV(hwReport.rows as unknown as Record<string, unknown>[], "homework_report.csv")}
                    className="flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm hover:bg-slate-50">
                    <Download size={14} /> Export CSV
                  </button>
                </div>

                {hwReport.rows.length === 0 ? (
                  <Card><p className="py-8 text-center text-sm text-slate-400">No homework assignments found for the selected filters.</p></Card>
                ) : (
                  <Card className="overflow-hidden p-0">
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-slate-100 bg-slate-50">
                            <th className="px-4 py-3 text-left text-xs font-medium text-slate-500">Title</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-slate-500">Subject</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-slate-500">Class</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-slate-500">Teacher</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-slate-500">Due</th>
                            <th className="px-4 py-3 text-center text-xs font-medium text-slate-500">Students</th>
                            <th className="px-4 py-3 text-center text-xs font-medium text-slate-500">Submitted</th>
                            <th className="px-4 py-3 text-center text-xs font-medium text-slate-500">Checked</th>
                            <th className="px-4 py-3 text-center text-xs font-medium text-slate-500">Pending</th>
                            <th className="px-4 py-3 text-center text-xs font-medium text-slate-500">Rate</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                          {hwReport.rows.map((r) => (
                            <tr key={r.assignment_id} className="hover:bg-slate-50 transition">
                              <td className="px-4 py-2.5 font-medium text-slate-900 max-w-40 truncate">{r.title}</td>
                              <td className="px-4 py-2.5 text-slate-600">{r.subject_name ?? "—"}</td>
                              <td className="px-4 py-2.5 text-slate-600">
                                {r.class_name}{r.section_name ? ` - ${r.section_name}` : ""}
                              </td>
                              <td className="px-4 py-2.5 text-slate-500">{r.teacher_name ?? "—"}</td>
                              <td className="px-4 py-2.5 text-xs text-slate-500">{fmt(r.due_date)}</td>
                              <td className="px-4 py-2.5 text-center text-slate-600">{r.total_students}</td>
                              <td className="px-4 py-2.5 text-center font-medium text-emerald-600">{r.submitted}</td>
                              <td className="px-4 py-2.5 text-center font-medium text-blue-600">{r.checked}</td>
                              <td className="px-4 py-2.5 text-center font-medium text-amber-600">{r.pending}</td>
                              <td className="px-4 py-2.5 text-center">
                                <div className="flex items-center gap-2 justify-center">
                                  <div className="w-16 h-1.5 rounded-full bg-slate-200">
                                    <div
                                      className={`h-1.5 rounded-full ${r.submission_rate >= 75 ? "bg-emerald-500" : r.submission_rate >= 50 ? "bg-amber-400" : "bg-red-400"}`}
                                      style={{ width: `${r.submission_rate}%` }}
                                    />
                                  </div>
                                  <span className="text-xs font-medium text-slate-600">{r.submission_rate}%</span>
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </Card>
                )}
              </>
            )}
            {!hwReport && !loading && (
              <Card><p className="py-8 text-center text-sm text-slate-400">Click "Load Report" to generate the homework report.</p></Card>
            )}
          </div>
        )}
      </div>
    </AppShell>
  );
}

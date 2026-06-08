"use client";

import { useEffect, useState } from "react";
import {
  AlertTriangle, BookUser, CheckCircle2, ChevronDown,
  Clock, RefreshCw, Save, XCircle,
} from "lucide-react";

import AppShell from "@/components/AppShell";
import { Button, Card, Input, Label } from "@/components/ui";
import { apiFetch, getSavedAuth, getSelectedAcademicSessionId, setSelectedAcademicSessionId } from "@/lib/api";
import type { AcademicSession, Section } from "@/types";

type AllowedClass = { id: number; name: string };

type DayRecord = {
  student_id: number;
  student_name: string;
  admission_no: string;
  roll_number?: string | null;
  status: string | null;
  note: string | null;
  attendance_id: number | null;
};

type Summary = {
  student_id: number;
  student_name: string;
  admission_no: string;
  total_days: number;
  present: number;
  absent: number;
  leave: number;
  half_day: number;
  percentage: number;
  low_attendance: boolean;
};

const STATUS_OPTIONS = ["PRESENT", "ABSENT", "LEAVE", "HALF_DAY"] as const;
type AttStatus = (typeof STATUS_OPTIONS)[number];

const STATUS_META: Record<AttStatus, { label: string; color: string; icon: React.ElementType }> = {
  PRESENT:  { label: "Present",  color: "bg-emerald-100 text-emerald-700 border-emerald-200", icon: CheckCircle2 },
  ABSENT:   { label: "Absent",   color: "bg-red-100 text-red-700 border-red-200",             icon: XCircle },
  LEAVE:    { label: "Leave",    color: "bg-amber-100 text-amber-700 border-amber-200",        icon: Clock },
  HALF_DAY: { label: "Half Day", color: "bg-blue-100 text-blue-700 border-blue-200",           icon: ChevronDown },
};

function today() {
  return new Date().toISOString().split("T")[0];
}

export default function AttendancePage() {
  const role = getSavedAuth()?.user?.role ?? "";
  const isTeacher = role === "TEACHER";

  const [tab, setTab] = useState<"mark" | "summary">("mark");

  // filter state
  const [sessions, setSessions]   = useState<AcademicSession[]>([]);
  const [classes, setClasses]     = useState<AllowedClass[]>([]);
  const [sections, setSections]   = useState<Section[]>([]);
  const [sessionId, setSessionId] = useState("");
  const [classId, setClassId]     = useState("");
  const [sectionId, setSectionId] = useState("");
  const [date, setDate]           = useState(today());

  // loading / error states
  const [loadingInit, setLoadingInit]     = useState(true);
  const [notAssigned, setNotAssigned]     = useState(false);   // teacher with zero classes
  const [loadingSheet, setLoadingSheet]   = useState(false);
  const [saving, setSaving]               = useState(false);
  const [loadingSummary, setLoadingSummary] = useState(false);
  const [saveMsg, setSaveMsg]             = useState("");
  const [error, setError]                 = useState("");

  // data
  const [sheet, setSheet]     = useState<DayRecord[]>([]);
  const [statuses, setStatuses] = useState<Record<number, AttStatus>>({});
  const [notes, setNotes]       = useState<Record<number, string>>({});
  const [summary, setSummary]   = useState<Summary[]>([]);

  // ── Initial load: sessions + allowed classes ────────────────────────────
  useEffect(() => {
    setLoadingInit(true);
    Promise.all([
      apiFetch<AcademicSession[]>("/academic-sessions"),
      apiFetch<AllowedClass[]>("/attendance/my-classes"),
    ])
      .then(([s, c]) => {
        setSessions(s);
        setClasses(c);

        const savedId = getSelectedAcademicSessionId();
        const saved = savedId ? s.find((x) => String(x.id) === savedId) : null;
        const active = s.find((x) => x.is_active);
        const selected = saved || active;
        if (selected) setSessionId(String(selected.id));

        if (isTeacher && c.length === 0) {
          // teacher has no class assignments at all
          setNotAssigned(true);
        } else if (c.length === 1) {
          // auto-select the only available class
          setClassId(String(c[0].id));
        }
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoadingInit(false));
  }, []);

  // ── Load sections when class changes ───────────────────────────────────
  useEffect(() => {
    if (!classId) { setSections([]); setSectionId(""); return; }
    apiFetch<Section[]>("/sections")
      .then((all) => {
        setSections(all.filter((s) => s.class_id === Number(classId)));
        setSectionId("");
      })
      .catch(() => setSections([]));
  }, [classId]);

  const canLoad = sessionId && classId && date;

  // ── Load sheet ──────────────────────────────────────────────────────────
  const loadSheet = async () => {
    if (!canLoad) return;
    setLoadingSheet(true);
    setError("");
    setSaveMsg("");
    try {
      const p = new URLSearchParams({ session_id: sessionId, class_id: classId, date });
      if (sectionId) p.set("section_id", sectionId);
      const data = await apiFetch<DayRecord[]>(`/attendance/sheet?${p}`);
      setSheet(data);
      const s: Record<number, AttStatus> = {};
      const n: Record<number, string>    = {};
      data.forEach((r) => {
        s[r.student_id] = (r.status as AttStatus) || "PRESENT";
        n[r.student_id] = r.note || "";
      });
      setStatuses(s);
      setNotes(n);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load sheet");
    } finally {
      setLoadingSheet(false);
    }
  };

  // ── Load summary ────────────────────────────────────────────────────────
  const loadSummary = async () => {
    if (!canLoad) return;
    setLoadingSummary(true);
    setError("");
    try {
      const p = new URLSearchParams({ session_id: sessionId, class_id: classId });
      if (sectionId) p.set("section_id", sectionId);
      setSummary(await apiFetch<Summary[]>(`/attendance/summary?${p}`));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load summary");
    } finally {
      setLoadingSummary(false);
    }
  };

  const markAll = (s: AttStatus) => {
    const u: Record<number, AttStatus> = {};
    sheet.forEach((r) => { u[r.student_id] = s; });
    setStatuses(u);
  };

  // ── Save attendance ─────────────────────────────────────────────────────
  const saveAttendance = async () => {
    if (!canLoad || sheet.length === 0) return;
    setSaving(true);
    setSaveMsg("");
    setError("");
    try {
      const entries = sheet.map((r) => ({
        student_id: r.student_id,
        status: statuses[r.student_id] || "PRESENT",
        note: notes[r.student_id] || null,
      }));
      await apiFetch("/attendance/bulk", {
        method: "POST",
        body: JSON.stringify({
          session_id: Number(sessionId),
          class_id:   Number(classId),
          section_id: sectionId ? Number(sectionId) : null,
          date,
          entries,
        }),
      });
      setSaveMsg("Attendance saved successfully!");
      await loadSheet();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const lowCount = summary.filter((s) => s.low_attendance).length;

  // ── Loading state ───────────────────────────────────────────────────────
  if (loadingInit) {
    return (
      <AppShell>
        <div className="flex items-center justify-center py-24">
          <RefreshCw className="animate-spin text-slate-400" size={28} />
        </div>
      </AppShell>
    );
  }

  // ── Teacher not assigned to any class ───────────────────────────────────
  if (notAssigned) {
    return (
      <AppShell>
        <div className="space-y-4">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Attendance</h1>
            <p className="mt-1 text-sm text-slate-500">Mark daily attendance and view student summaries</p>
          </div>
          <Card>
            <div className="flex flex-col items-center gap-4 py-12 text-center">
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-amber-50">
                <BookUser size={32} className="text-amber-500" />
              </div>
              <div>
                <p className="text-base font-semibold text-slate-800">You are not assigned to any class</p>
                <p className="mt-1 text-sm text-slate-500">
                  Ask your admin to assign you as a class teacher or subject teacher for a class.
                  Once assigned, the attendance sheet will appear here.
                </p>
              </div>
            </div>
          </Card>
        </div>
      </AppShell>
    );
  }

  // ── Main UI ─────────────────────────────────────────────────────────────
  return (
    <AppShell>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Attendance</h1>
          <p className="mt-1 text-sm text-slate-500">Mark daily attendance and view student summaries</p>
        </div>

        {error && (
          <div className="flex items-center gap-2 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700 border border-red-200">
            <AlertTriangle size={16} /> {error}
          </div>
        )}

        {/* Filter bar */}
        <Card>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {/* Session */}
            <div>
              <Label>Academic session</Label>
              <select
                className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm outline-none focus:border-slate-400"
                value={sessionId}
                onChange={(e) => { setSessionId(e.target.value); setSelectedAcademicSessionId(e.target.value); }}
              >
                <option value="">Select session</option>
                {sessions.map((s) => (
                  <option key={s.id} value={s.id}>{s.name}{s.is_active ? " (Active)" : ""}</option>
                ))}
              </select>
            </div>

            {/* Class — only shows assigned classes for teachers */}
            <div>
              <Label>
                Class
                {isTeacher && classes.length > 0 && (
                  <span className="ml-2 text-xs text-slate-400">({classes.length} assigned)</span>
                )}
              </Label>
              <select
                className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm outline-none focus:border-slate-400"
                value={classId}
                onChange={(e) => setClassId(e.target.value)}
              >
                <option value="">Select class</option>
                {classes.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>

            {/* Section */}
            <div>
              <Label>Section (optional)</Label>
              <select
                className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm outline-none focus:border-slate-400"
                value={sectionId}
                onChange={(e) => setSectionId(e.target.value)}
                disabled={!classId}
              >
                <option value="">All sections</option>
                {sections.map((s) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            </div>

            {/* Date */}
            <div>
              <Label>Date</Label>
              <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} max={today()} />
            </div>
          </div>
        </Card>

        {/* Tabs */}
        <div className="flex gap-2 border-b border-slate-200">
          {(["mark", "summary"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-2 text-sm font-medium capitalize transition border-b-2 -mb-px ${
                tab === t
                  ? "border-slate-900 text-slate-900"
                  : "border-transparent text-slate-500 hover:text-slate-700"
              }`}
            >
              {t === "mark" ? "Mark Attendance" : "Summary & Report"}
            </button>
          ))}
        </div>

        {/* ── MARK TAB ──────────────────────────────────────────────────── */}
        {tab === "mark" && (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-3">
              <Button onClick={loadSheet} disabled={!canLoad || loadingSheet} className="flex items-center gap-2">
                <RefreshCw size={15} className={loadingSheet ? "animate-spin" : ""} />
                {loadingSheet ? "Loading..." : "Load Students"}
              </Button>
              {sheet.length > 0 && (
                <>
                  <span className="text-xs text-slate-400">Mark all as:</span>
                  {STATUS_OPTIONS.map((s) => (
                    <button
                      key={s}
                      onClick={() => markAll(s)}
                      className={`rounded-full border px-3 py-1 text-xs font-medium transition ${STATUS_META[s].color}`}
                    >
                      {STATUS_META[s].label}
                    </button>
                  ))}
                </>
              )}
            </div>

            {saveMsg && (
              <div className="flex items-center gap-2 rounded-xl bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
                <CheckCircle2 size={16} /> {saveMsg}
              </div>
            )}

            {sheet.length === 0 && !loadingSheet && (
              <Card>
                <p className="py-8 text-center text-sm text-slate-400">
                  Select a session, class and date, then click "Load Students"
                </p>
              </Card>
            )}

            {sheet.length > 0 && (
              <>
                <Card className="overflow-hidden p-0">
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-slate-100 bg-slate-50">
                          <th className="px-4 py-3 text-left font-medium text-slate-500">#</th>
                          <th className="px-4 py-3 text-left font-medium text-slate-500">Student</th>
                          <th className="px-4 py-3 text-left font-medium text-slate-500">Admission No</th>
                          <th className="px-4 py-3 text-left font-medium text-slate-500">Status</th>
                          <th className="px-4 py-3 text-left font-medium text-slate-500">Note</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {sheet.map((row, idx) => {
                          const current = statuses[row.student_id] || "PRESENT";
                          return (
                            <tr key={row.student_id} className="hover:bg-slate-50 transition">
                              <td className="px-4 py-3 text-slate-400 text-xs">{idx + 1}</td>
                              <td className="px-4 py-3">
                                <p className="font-medium text-slate-900">{row.student_name}</p>
                                {row.roll_number && (
                                  <p className="text-xs text-slate-400">Roll {row.roll_number}</p>
                                )}
                              </td>
                              <td className="px-4 py-3 font-mono text-xs text-slate-600">{row.admission_no}</td>
                              <td className="px-4 py-3">
                                <div className="flex flex-wrap gap-1">
                                  {STATUS_OPTIONS.map((s) => {
                                    const meta   = STATUS_META[s];
                                    const active = current === s;
                                    return (
                                      <button
                                        key={s}
                                        onClick={() => setStatuses((prev) => ({ ...prev, [row.student_id]: s }))}
                                        className={`rounded-full border px-2.5 py-0.5 text-xs font-medium transition ${
                                          active
                                            ? meta.color + " ring-1 ring-current"
                                            : "border-slate-200 text-slate-400 hover:border-slate-300"
                                        }`}
                                      >
                                        {meta.label}
                                      </button>
                                    );
                                  })}
                                </div>
                              </td>
                              <td className="px-4 py-3">
                                <input
                                  type="text"
                                  placeholder="Optional note"
                                  value={notes[row.student_id] || ""}
                                  onChange={(e) => setNotes((prev) => ({ ...prev, [row.student_id]: e.target.value }))}
                                  className="w-36 rounded-lg border border-slate-200 px-2 py-1 text-xs outline-none focus:border-slate-400"
                                />
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </Card>

                <div className="flex items-center justify-between">
                  <p className="text-sm text-slate-500">{sheet.length} students</p>
                  <Button onClick={saveAttendance} disabled={saving} className="flex items-center gap-2">
                    <Save size={15} />
                    {saving ? "Saving..." : "Save Attendance"}
                  </Button>
                </div>
              </>
            )}
          </div>
        )}

        {/* ── SUMMARY TAB ───────────────────────────────────────────────── */}
        {tab === "summary" && (
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              <Button onClick={loadSummary} disabled={!canLoad || loadingSummary} className="flex items-center gap-2">
                <RefreshCw size={15} className={loadingSummary ? "animate-spin" : ""} />
                {loadingSummary ? "Loading..." : "Load Summary"}
              </Button>
            </div>

            {summary.length === 0 && !loadingSummary && (
              <Card>
                <p className="py-8 text-center text-sm text-slate-400">
                  Select a session and class, then click "Load Summary"
                </p>
              </Card>
            )}

            {summary.length > 0 && (
              <>
                {lowCount > 0 && (
                  <div className="flex items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
                    <AlertTriangle size={16} />
                    <strong>{lowCount} student{lowCount > 1 ? "s" : ""}</strong> below 75% attendance
                  </div>
                )}

                <div className="grid gap-4 sm:grid-cols-4">
                  {[
                    { label: "Total students",       value: summary.length,                                                                                    color: "text-slate-900" },
                    { label: "Avg attendance",        value: `${(summary.reduce((a, s) => a + s.percentage, 0) / summary.length).toFixed(1)}%`,                color: "text-emerald-600" },
                    { label: "Low attendance (<75%)", value: lowCount,                                                                                         color: "text-amber-600" },
                    { label: "Total days tracked",    value: summary[0]?.total_days ?? 0,                                                                      color: "text-slate-600" },
                  ].map((stat) => (
                    <Card key={stat.label}>
                      <p className="text-xs text-slate-500">{stat.label}</p>
                      <p className={`mt-1 text-2xl font-bold ${stat.color}`}>{stat.value}</p>
                    </Card>
                  ))}
                </div>

                <Card className="overflow-hidden p-0">
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-slate-100 bg-slate-50">
                          <th className="px-4 py-3 text-left font-medium text-slate-500">Student</th>
                          <th className="px-4 py-3 text-center font-medium text-slate-500">Total</th>
                          <th className="px-4 py-3 text-center font-medium text-emerald-600">Present</th>
                          <th className="px-4 py-3 text-center font-medium text-red-500">Absent</th>
                          <th className="px-4 py-3 text-center font-medium text-amber-500">Leave</th>
                          <th className="px-4 py-3 text-center font-medium text-blue-500">Half Day</th>
                          <th className="px-4 py-3 text-center font-medium text-slate-500">%</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {summary.map((s) => (
                          <tr
                            key={s.student_id}
                            className={`transition ${s.low_attendance ? "bg-amber-50" : "hover:bg-slate-50"}`}
                          >
                            <td className="px-4 py-3">
                              <div className="flex items-center gap-2">
                                {s.low_attendance && <AlertTriangle size={14} className="shrink-0 text-amber-500" />}
                                <div>
                                  <p className="font-medium text-slate-900">{s.student_name}</p>
                                  <p className="text-xs text-slate-400">{s.admission_no}</p>
                                </div>
                              </div>
                            </td>
                            <td className="px-4 py-3 text-center text-slate-600">{s.total_days}</td>
                            <td className="px-4 py-3 text-center font-medium text-emerald-600">{s.present}</td>
                            <td className="px-4 py-3 text-center font-medium text-red-500">{s.absent}</td>
                            <td className="px-4 py-3 text-center font-medium text-amber-500">{s.leave}</td>
                            <td className="px-4 py-3 text-center font-medium text-blue-500">{s.half_day}</td>
                            <td className="px-4 py-3 text-center">
                              <span
                                className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                                  s.low_attendance
                                    ? "bg-amber-100 text-amber-700"
                                    : s.percentage >= 90
                                    ? "bg-emerald-100 text-emerald-700"
                                    : "bg-slate-100 text-slate-600"
                                }`}
                              >
                                {s.percentage}%
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </Card>
              </>
            )}
          </div>
        )}
      </div>
    </AppShell>
  );
}

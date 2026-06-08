"use client";

import { useEffect, useState } from "react";
import {
  AlertTriangle,
  CalendarDays,
  CheckCircle2,
  Clock,
  RefreshCw,
  TrendingUp,
  XCircle,
} from "lucide-react";

import AppShell from "@/components/AppShell";
import { Card, Label } from "@/components/ui";
import { apiFetch, getSavedAuth, getSelectedAcademicSessionId, setSelectedAcademicSessionId } from "@/lib/api";
import type { AcademicSession } from "@/types";

type AttendanceRecord = {
  id: number;
  student_id: number;
  student_name?: string | null;
  date: string;
  status: string;
  note?: string | null;
};

const STATUS_META: Record<
  string,
  { label: string; color: string; dot: string; icon: React.ElementType }
> = {
  PRESENT: {
    label: "Present",
    color: "bg-emerald-100 text-emerald-700",
    dot: "bg-emerald-500",
    icon: CheckCircle2,
  },
  ABSENT: {
    label: "Absent",
    color: "bg-red-100 text-red-600",
    dot: "bg-red-500",
    icon: XCircle,
  },
  LEAVE: {
    label: "Leave",
    color: "bg-amber-100 text-amber-700",
    dot: "bg-amber-400",
    icon: Clock,
  },
  HALF_DAY: {
    label: "Half Day",
    color: "bg-blue-100 text-blue-700",
    dot: "bg-blue-400",
    icon: CalendarDays,
  },
};

function formatDate(dateStr: string) {
  const d = new Date(dateStr);
  return d.toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    weekday: "short",
  });
}

function groupByMonth(records: AttendanceRecord[]) {
  const map = new Map<string, AttendanceRecord[]>();
  for (const r of records) {
    const key = r.date.slice(0, 7); // "YYYY-MM"
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(r);
  }
  return map;
}

function groupByStudent(records: AttendanceRecord[]) {
  const map = new Map<number, { name: string; records: AttendanceRecord[] }>();
  for (const r of records) {
    const name = r.student_name || `Student ${r.student_id}`;
    if (!map.has(r.student_id)) {
      map.set(r.student_id, { name, records: [] });
    }
    map.get(r.student_id)!.records.push(r);
  }
  return map;
}

function monthLabel(key: string) {
  const [y, m] = key.split("-");
  return new Date(Number(y), Number(m) - 1).toLocaleDateString("en-IN", {
    month: "long",
    year: "numeric",
  });
}

export default function MyAttendancePage() {
  const [sessions, setSessions] = useState<AcademicSession[]>([]);
  const [sessionId, setSessionId] = useState("");
  const [records, setRecords] = useState<AttendanceRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [isParent, setIsParent] = useState(false);

  useEffect(() => {
    const auth = getSavedAuth();
    setIsParent(auth?.user.role === "PARENT");

    apiFetch<AcademicSession[]>("/academic-sessions")
      .then((s) => {
        setSessions(s);
        const savedId = getSelectedAcademicSessionId();
        const saved = savedId ? s.find((x) => String(x.id) === savedId) : null;
        const active = s.find((x) => x.is_active);
        const selected = saved || active;
        if (selected) {
          setSessionId(String(selected.id));
        }
      })
      .catch((e) => setError(e.message));
  }, []);

  // auto-load when session is selected
  useEffect(() => {
    if (!sessionId) return;
    load(sessionId);
  }, [sessionId]);

  const load = async (sid: string) => {
    setLoading(true);
    setError("");
    try {
      const data = await apiFetch<AttendanceRecord[]>(
        `/attendance/my?session_id=${sid}`,
      );
      // sort newest first
      data.sort((a, b) => b.date.localeCompare(a.date));
      setRecords(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load attendance");
    } finally {
      setLoading(false);
    }
  };

  // stats
  const total = records.length;
  const present = records.filter((r) => r.status === "PRESENT").length;
  const absent = records.filter((r) => r.status === "ABSENT").length;
  const leave = records.filter((r) => r.status === "LEAVE").length;
  const halfDay = records.filter((r) => r.status === "HALF_DAY").length;
  const effective = present + halfDay * 0.5;
  const pct = total > 0 ? Math.round((effective / total) * 100 * 10) / 10 : 0;
  const lowAtt = total > 0 && pct < 75;

  const grouped = isParent ? groupByStudent(records) : groupByMonth(records);

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            {isParent ? "Child Attendance" : "My Attendance"}
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            {isParent
              ? "View your children's attendance record for the selected session"
              : "View your attendance record for the selected session"}
          </p>
        </div>

        {error && (
          <div className="flex items-center gap-2 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">
            <AlertTriangle size={16} /> {error}
          </div>
        )}

        {/* Session selector */}
        <Card>
          <div className="flex items-end gap-4">
            <div className="flex-1 max-w-xs">
              <Label>Academic session</Label>
              <select
                className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm outline-none focus:border-slate-400"
                value={sessionId}
                onChange={(e) => { setSessionId(e.target.value); setSelectedAcademicSessionId(e.target.value); }}
              >
                <option value="">Select session</option>
                {sessions.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                    {s.is_active ? " (Active)" : ""}
                  </option>
                ))}
              </select>
            </div>
            <button
              onClick={() => load(sessionId)}
              disabled={!sessionId || loading}
              className="flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
              Refresh
            </button>
          </div>
        </Card>

        {/* Stat cards - only for students */}
        {!isParent && total > 0 && (
          <>
            {lowAtt && (
              <div className="flex items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
                <AlertTriangle size={16} />
                Your attendance is <strong>{pct}%</strong> — below the required
                75%. Please regularise.
              </div>
            )}

            <div className="grid gap-4 grid-cols-2 sm:grid-cols-5">
              {/* Percentage — big card */}
              <div
                className={`col-span-2 sm:col-span-1 flex flex-col items-center justify-center rounded-2xl border p-5 ${
                  lowAtt
                    ? "border-amber-200 bg-amber-50"
                    : pct >= 90
                      ? "border-emerald-200 bg-emerald-50"
                      : "border-slate-200 bg-white"
                }`}
              >
                <TrendingUp
                  size={22}
                  className={lowAtt ? "text-amber-500" : "text-emerald-500"}
                />
                <p
                  className={`mt-2 text-3xl font-bold ${lowAtt ? "text-amber-600" : "text-slate-900"}`}
                >
                  {pct}%
                </p>
                <p className="mt-1 text-xs text-slate-500">Attendance</p>
              </div>

              {[
                { label: "Total days", value: total, color: "text-slate-700" },
                { label: "Present", value: present, color: "text-emerald-600" },
                { label: "Absent", value: absent, color: "text-red-500" },
                {
                  label: "Leave / Half-Day",
                  value: `${leave} / ${halfDay}`,
                  color: "text-amber-600",
                },
              ].map((s) => (
                <Card
                  key={s.label}
                  className="flex flex-col items-center justify-center text-center"
                >
                  <p className={`text-2xl font-bold ${s.color}`}>{s.value}</p>
                  <p className="mt-1 text-xs text-slate-500">{s.label}</p>
                </Card>
              ))}
            </div>
          </>
        )}

        {/* Month-wise or Student-wise records */}
        {records.length === 0 && !loading && sessionId && (
          <Card>
            <p className="py-8 text-center text-sm text-slate-400">
              No attendance records found for this session.
            </p>
          </Card>
        )}

        {isParent && (
          <>
            {Array.from(groupByStudent(records).entries()).map(
              ([studentId, { name, records: studentRecords }]) => {
                const studentRecordsByMonth = groupByMonth(studentRecords);

                const sTotal = studentRecords.length;
                const sPresent = studentRecords.filter(
                  (r) => r.status === "PRESENT",
                ).length;
                const sHalfDay = studentRecords.filter(
                  (r) => r.status === "HALF_DAY",
                ).length;

                const sEffective = sPresent + sHalfDay * 0.5;

                const sPct =
                  sTotal > 0
                    ? Math.round((sEffective / sTotal) * 100 * 10) / 10
                    : 0;
                return (
                  <div
                    key={studentId}
                    className="space-y-4 rounded-xl border border-slate-200 p-4 bg-white"
                  >
                    {/* Student header */}
                    <div className="flex items-center justify-between">
                      <div>
                        <h2 className="font-semibold text-slate-900">{name}</h2>
                        <p className="text-sm text-slate-500 mt-1">
                          {sTotal} total records
                        </p>
                      </div>
                      <div
                        className={`text-2xl font-bold ${lowAtt ? "text-amber-600" : sPct >= 90 ? "text-emerald-600" : "text-slate-700"}`}
                      >
                        {sPct}%
                      </div>
                    </div>

                    {/* Month-wise details */}
                    <div className="space-y-4">
                      {Array.from(studentRecordsByMonth.entries()).map(
                        ([monthKey, monthRecords]) => {
                          const mTotal = monthRecords.length;
                          const mPresent = monthRecords.filter(
                            (r) => r.status === "PRESENT",
                          ).length;
                          const mPct =
                            mTotal > 0
                              ? Math.round((mPresent / mTotal) * 100)
                              : 0;

                          return (
                            <div key={monthKey} className="space-y-2">
                              {/* Month header */}
                              <div className="flex items-center justify-between">
                                <h3 className="text-sm font-semibold text-slate-700">
                                  {monthLabel(monthKey)}
                                </h3>
                                <span
                                  className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                                    mPct < 75
                                      ? "bg-amber-100 text-amber-700"
                                      : mPct >= 90
                                        ? "bg-emerald-100 text-emerald-700"
                                        : "bg-slate-100 text-slate-600"
                                  }`}
                                >
                                  {mPresent}/{mTotal} present · {mPct}%
                                </span>
                              </div>

                              <Card className="overflow-hidden p-0">
                                <div className="divide-y divide-slate-100">
                                  {monthRecords.map((r) => {
                                    const meta =
                                      STATUS_META[r.status] ??
                                      STATUS_META["ABSENT"];
                                    const Icon = meta.icon;
                                    return (
                                      <div
                                        key={r.id}
                                        className="flex items-center gap-3 px-4 py-3 hover:bg-slate-50 transition"
                                      >
                                        <div
                                          className={`h-2 w-2 rounded-full shrink-0 ${meta.dot}`}
                                        />
                                        <p className="flex-1 text-sm text-slate-700">
                                          {formatDate(r.date)}
                                        </p>
                                        <span
                                          className={`flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${meta.color}`}
                                        >
                                          <Icon size={11} />
                                          {meta.label}
                                        </span>
                                        {r.note && (
                                          <p className="text-xs text-slate-400 italic truncate max-w-30">
                                            {r.note}
                                          </p>
                                        )}
                                      </div>
                                    );
                                  })}
                                </div>
                              </Card>
                            </div>
                          );
                        },
                      )}
                    </div>
                  </div>
                );
              },
            )}
          </>
        )}

        {!isParent &&
          grouped.size > 0 &&
          Array.from(groupByMonth(records).entries()).map(
            ([monthKey, monthRecords]) => {
              const mTotal = monthRecords.length;
              const mPresent = monthRecords.filter(
                (r) => r.status === "PRESENT",
              ).length;

              const mPct =
                mTotal > 0 ? Math.round((mPresent / mTotal) * 100) : 0;

              return (
                <div key={monthKey} className="space-y-2">
                  {/* Month header */}
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-semibold text-slate-700">
                      {monthLabel(monthKey)}
                    </h3>
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                        mPct < 75
                          ? "bg-amber-100 text-amber-700"
                          : mPct >= 90
                            ? "bg-emerald-100 text-emerald-700"
                            : "bg-slate-100 text-slate-600"
                      }`}
                    >
                      {mPresent}/{mTotal} present · {mPct}%
                    </span>
                  </div>

                  <Card className="overflow-hidden p-0">
                    <div className="divide-y divide-slate-100">
                      {monthRecords.map((r) => {
                        const meta =
                          STATUS_META[r.status] ?? STATUS_META["ABSENT"];
                        const Icon = meta.icon;
                        return (
                          <div
                            key={r.id}
                            className="flex items-center gap-3 px-4 py-3 hover:bg-slate-50 transition"
                          >
                            <div
                              className={`h-2 w-2 rounded-full shrink-0 ${meta.dot}`}
                            />
                            <p className="flex-1 text-sm text-slate-700">
                              {formatDate(r.date)}
                            </p>
                            <span
                              className={`flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${meta.color}`}
                            >
                              <Icon size={11} />
                              {meta.label}
                            </span>
                            {r.note && (
                              <p className="text-xs text-slate-400 italic truncate max-w-30">
                                {r.note}
                              </p>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </Card>
                </div>
              );
            },
          )}
      </div>
    </AppShell>
  );
}

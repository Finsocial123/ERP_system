"use client";

import { useEffect, useMemo, useState } from "react";
import { CalendarDays, Clock, MapPin, RefreshCcw } from "lucide-react";

import { Button, Card } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import type { ExamTimetableItem, StudentReportCard } from "@/types";

function statusClass(status: string) {
  if (status === "PASS" || status === "PUBLISHED" || status === "MANUAL") return "bg-emerald-50 text-emerald-700";
  if (status === "FAIL" || status === "ABSENT") return "bg-red-50 text-red-700";
  if (status === "AUTO_FROM_EXAM_START") return "bg-sky-50 text-sky-700";
  return "bg-amber-50 text-amber-700";
}

function formatDate(value?: string | null) {
  return value ? value.slice(0, 10) : "-";
}

function formatTime(value?: string | null) {
  return value ? value.slice(0, 5) : "-";
}

export default function ReportCards({ role }: { role: "student" | "parent" }) {
  const [cards, setCards] = useState<StudentReportCard[]>([]);
  const [timetable, setTimetable] = useState<ExamTimetableItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const groupedCards = useMemo(() => {
    const map = new Map<string, StudentReportCard[]>();
    cards.forEach((card) => {
      const key = role === "parent" ? `${card.student_name} · ${card.admission_no}` : "My Report Cards";
      map.set(key, [...(map.get(key) || []), card]);
    });
    return Array.from(map.entries());
  }, [cards, role]);

  const groupedTimetable = useMemo(() => {
    const map = new Map<string, ExamTimetableItem[]>();
    timetable.forEach((row) => {
      const studentPrefix = role === "parent" ? `${row.student_name || "Student"} · ${row.admission_no || ""} · ` : "";
      const section = row.section_name ? ` - ${row.section_name}` : "";
      const key = `${studentPrefix}${row.exam_name} · ${row.class_name || "Class"}${section}`;
      map.set(key, [...(map.get(key) || []), row]);
    });
    return Array.from(map.entries()).map(([key, rows]) => [
      key,
      rows.sort((a, b) => `${a.exam_date || "9999"}${a.start_time || ""}`.localeCompare(`${b.exam_date || "9999"}${b.start_time || ""}`)),
    ]) as [string, ExamTimetableItem[]][];
  }, [role, timetable]);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const reportEndpoint = role === "parent" ? "/exams/my-children-report-cards" : "/exams/my-report-cards";
      const timetableEndpoint = role === "parent" ? "/exams/my-children-timetable" : "/exams/my-timetable";
      const [reportData, timetableData] = await Promise.all([
        apiFetch<StudentReportCard[]>(reportEndpoint),
        apiFetch<ExamTimetableItem[]>(timetableEndpoint),
      ]);
      setCards(reportData);
      setTimetable(timetableData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load exam data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [role]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-3 md:flex-row md:items-center">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{role === "parent" ? "Child Exams" : "My Exams"}</h1>
          <p className="text-sm text-slate-500">View exam timetable first. Published results appear below after admin/teacher publishes them.</p>
        </div>
        <Button onClick={load} disabled={loading} className="flex items-center gap-2">
          <RefreshCcw size={16} /> Refresh
        </Button>
      </div>

      {error && <div className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</div>}
      {loading && <Card>Loading exams...</Card>}

      {!loading && (
        <section className="space-y-4">
          <div className="flex items-center gap-2">
            <CalendarDays size={20} className="text-slate-500" />
            <h2 className="text-lg font-bold text-slate-900">Exam Timetable</h2>
          </div>
          {timetable.length === 0 && <Card>No exam timetable found yet.</Card>}
          {groupedTimetable.map(([groupTitle, rows]) => (
            <Card key={groupTitle} className="space-y-4">
              <div className="flex flex-col justify-between gap-2 md:flex-row md:items-start">
                <div>
                  <h3 className="text-lg font-bold text-slate-900">{groupTitle}</h3>
                  <p className="text-sm text-slate-500">{rows[0]?.exam_type || "Exam"} · Result status: {rows[0]?.result_status}</p>
                </div>
                <span className={`w-fit rounded-full px-3 py-1 text-xs font-semibold ${statusClass(rows[0]?.result_status || "DRAFT")}`}>{rows[0]?.result_status || "DRAFT"}</span>
              </div>

              <div className="overflow-x-auto rounded-2xl border border-slate-200">
                <table className="min-w-full divide-y divide-slate-200 text-sm">
                  <thead className="bg-slate-50 text-left text-slate-600">
                    <tr>
                      <th className="px-4 py-3">Date</th>
                      <th className="px-4 py-3">Time</th>
                      <th className="px-4 py-3">Subject</th>
                      <th className="px-4 py-3">Teacher</th>
                      <th className="px-4 py-3">Room</th>
                      <th className="px-4 py-3">Instructions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {rows.map((row) => (
                      <tr key={`${groupTitle}-${row.exam_subject_id}`}>
                        <td className="px-4 py-3 font-semibold text-slate-900">{formatDate(row.exam_date)}</td>
                        <td className="px-4 py-3 text-slate-600"><span className="inline-flex items-center gap-1"><Clock size={14} /> {formatTime(row.start_time)} - {formatTime(row.end_time)}</span></td>
                        <td className="px-4 py-3"><p className="font-semibold text-slate-900">{row.subject_name || "Subject"}</p><p className="text-xs text-slate-500">Max {row.max_marks} · Pass {row.pass_marks}</p></td>
                        <td className="px-4 py-3 text-slate-600">{row.teacher_name || "-"}</td>
                        <td className="px-4 py-3 text-slate-600"><span className="inline-flex items-center gap-1"><MapPin size={14} /> {row.room || "-"}</span></td>
                        <td className="px-4 py-3 text-slate-500">{row.timetable_note || "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          ))}
        </section>
      )}

      {!loading && (
        <section className="space-y-4">
          <h2 className="text-lg font-bold text-slate-900">Published Report Cards</h2>
          {cards.length === 0 && <Card>No published results found yet.</Card>}

          {groupedCards.map(([groupTitle, groupCards]) => (
            <section key={groupTitle} className="space-y-4">
              {role === "parent" && <h3 className="text-base font-bold text-slate-900">{groupTitle}</h3>}
              {groupCards.map((card) => (
                <Card key={`${card.exam_id}-${card.student_id}`} className="space-y-4">
                  <div className="flex flex-col justify-between gap-3 md:flex-row md:items-start">
                    <div>
                      <h3 className="text-xl font-bold text-slate-900">{card.exam_name}</h3>
                      <p className="text-sm text-slate-500">{card.exam_type || "Exam"} · Published: {formatDate(card.published_at)}</p>
                      <p className="text-sm text-slate-600">{card.student_name} · {card.class_name || "Class"}{card.section_name ? ` - ${card.section_name}` : ""}</p>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-right md:min-w-64">
                      <div className="rounded-xl bg-slate-50 p-3">
                        <p className="text-xs text-slate-500">Marks</p>
                        <p className="text-lg font-bold text-slate-900">{card.marks_obtained}/{card.total_marks}</p>
                      </div>
                      <div className="rounded-xl bg-slate-50 p-3">
                        <p className="text-xs text-slate-500">Percentage</p>
                        <p className="text-lg font-bold text-slate-900">{card.percentage}%</p>
                      </div>
                      <div className="rounded-xl bg-slate-50 p-3">
                        <p className="text-xs text-slate-500">Grade</p>
                        <p className="text-lg font-bold text-slate-900">{card.grade}</p>
                      </div>
                      <div className="rounded-xl bg-slate-50 p-3">
                        <p className="text-xs text-slate-500">Status</p>
                        <span className={`inline-block rounded-full px-2 py-1 text-xs font-semibold ${statusClass(card.pass_status)}`}>{card.pass_status}</span>
                      </div>
                    </div>
                  </div>

                  <div className="overflow-x-auto rounded-2xl border border-slate-200">
                    <table className="min-w-full divide-y divide-slate-200 text-sm">
                      <thead className="bg-slate-50 text-left text-slate-600">
                        <tr>
                          <th className="px-4 py-3">Subject</th>
                          <th className="px-4 py-3">Marks</th>
                          <th className="px-4 py-3">Pass Marks</th>
                          <th className="px-4 py-3">Grade</th>
                          <th className="px-4 py-3">Status</th>
                          <th className="px-4 py-3">Remarks</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {card.subjects.map((subject) => (
                          <tr key={subject.exam_subject_id}>
                            <td className="px-4 py-3 font-semibold text-slate-900">{subject.subject_name}</td>
                            <td className="px-4 py-3 text-slate-600">{subject.is_absent ? "Absent" : subject.marks_obtained ?? "-"}/{subject.max_marks}</td>
                            <td className="px-4 py-3 text-slate-600">{subject.pass_marks}</td>
                            <td className="px-4 py-3 text-slate-600">{subject.grade || "-"}</td>
                            <td className="px-4 py-3"><span className={`rounded-full px-2 py-1 text-xs font-semibold ${statusClass(subject.pass_status)}`}>{subject.pass_status}</span></td>
                            <td className="px-4 py-3 text-slate-500">{subject.remarks || "-"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </Card>
              ))}
            </section>
          ))}
        </section>
      )}
    </div>
  );
}

"use client";

import { useEffect, useMemo, useState } from "react";
import { RefreshCcw } from "lucide-react";

import { Button, Card } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import type { StudentReportCard } from "@/types";

function statusClass(status: string) {
  if (status === "PASS" || status === "PUBLISHED") return "bg-emerald-50 text-emerald-700";
  if (status === "FAIL" || status === "ABSENT") return "bg-red-50 text-red-700";
  return "bg-amber-50 text-amber-700";
}

function formatDate(value?: string | null) {
  return value ? value.slice(0, 10) : "-";
}

export default function ReportCards({ role }: { role: "student" | "parent" }) {
  const [cards, setCards] = useState<StudentReportCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const grouped = useMemo(() => {
    const map = new Map<string, StudentReportCard[]>();
    cards.forEach((card) => {
      const key = role === "parent" ? `${card.student_name} · ${card.admission_no}` : "My Report Cards";
      map.set(key, [...(map.get(key) || []), card]);
    });
    return Array.from(map.entries());
  }, [cards, role]);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const endpoint = role === "parent" ? "/exams/my-children-report-cards" : "/exams/my-report-cards";
      const data = await apiFetch<StudentReportCard[]>(endpoint);
      setCards(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load report cards");
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
          <p className="text-sm font-semibold uppercase tracking-wide text-slate-400">Phase 8</p>
          <h1 className="text-2xl font-bold text-slate-900">{role === "parent" ? "Child Results" : "Report Cards"}</h1>
          <p className="text-sm text-slate-500">Only published exam results are shown here.</p>
        </div>
        <Button onClick={load} disabled={loading} className="flex items-center gap-2">
          <RefreshCcw size={16} /> Refresh
        </Button>
      </div>

      {error && <div className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</div>}
      {loading && <Card>Loading report cards...</Card>}
      {!loading && cards.length === 0 && <Card>No published results found yet.</Card>}

      {!loading && grouped.map(([groupTitle, groupCards]) => (
        <section key={groupTitle} className="space-y-4">
          {role === "parent" && <h2 className="text-lg font-bold text-slate-900">{groupTitle}</h2>}
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
    </div>
  );
}

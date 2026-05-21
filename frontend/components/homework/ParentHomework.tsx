"use client";

import { useEffect, useMemo, useState } from "react";
import { FileText, RefreshCcw } from "lucide-react";

import { AppSection } from "@/components/CrudManager";
import { Card } from "@/components/ui";
import { apiFetch, fileUrl } from "@/lib/api";
import type { ParentHomework as ParentHomeworkType } from "@/types";

function statusClass(status: string) {
  if (status === "CHECKED") return "bg-green-50 text-green-700";
  if (status === "SUBMITTED") return "bg-blue-50 text-blue-700";
  return "bg-amber-50 text-amber-700";
}

function formatDate(value?: string | null) {
  if (!value) return "-";
  return new Date(value).toLocaleDateString();
}

export default function ParentHomework() {
  const [rows, setRows] = useState<ParentHomeworkType[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadRows = async () => {
    setLoading(true);
    setError("");
    try {
      setRows(await apiFetch<ParentHomeworkType[]>("/homework/parent/assignments"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load homework");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRows();
  }, []);

  const counts = useMemo(() => {
    return rows.reduce(
      (acc, item) => {
        acc.total += 1;
        if (item.submission_status === "PENDING") acc.pending += 1;
        if (item.submission_status === "SUBMITTED") acc.submitted += 1;
        if (item.submission_status === "CHECKED") acc.checked += 1;
        return acc;
      },
      { total: 0, pending: 0, submitted: 0, checked: 0 }
    );
  }, [rows]);

  return (
    <AppSection title="Child Homework" description="Track homework assigned to your linked child profiles and see submission/checking status.">
      <div className="mb-6 grid gap-4 md:grid-cols-4">
        <Card><p className="text-sm text-slate-500">Total</p><p className="mt-2 text-3xl font-bold text-slate-900">{counts.total}</p></Card>
        <Card><p className="text-sm text-slate-500">Pending</p><p className="mt-2 text-3xl font-bold text-amber-700">{counts.pending}</p></Card>
        <Card><p className="text-sm text-slate-500">Submitted</p><p className="mt-2 text-3xl font-bold text-blue-700">{counts.submitted}</p></Card>
        <Card><p className="text-sm text-slate-500">Checked</p><p className="mt-2 text-3xl font-bold text-green-700">{counts.checked}</p></Card>
      </div>

      <Card>
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-bold text-slate-900">Homework Status</h2>
            <p className="text-sm text-slate-500">Read-only parent view.</p>
          </div>
          <button type="button" onClick={loadRows} className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"><RefreshCcw size={16} /> Refresh</button>
        </div>
        {error && <p className="mb-4 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
        {loading ? <p className="text-sm text-slate-500">Loading homework...</p> : rows.length === 0 ? <p className="text-sm text-slate-500">No homework found for linked children.</p> : (
          <div className="space-y-3">
            {rows.map((item) => (
              <div key={`${item.student_id}-${item.id}`} className="rounded-2xl border border-slate-200 bg-white p-4">
                <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                  <div>
                    <p className="text-sm font-semibold text-slate-500">{item.student_name} · {item.admission_no}</p>
                    <h3 className="mt-1 font-bold text-slate-900">{item.title}</h3>
                    <p className="mt-1 text-sm text-slate-500">{item.class_name || `Class ${item.class_id}`} {item.section_name ? `- ${item.section_name}` : ""} {item.subject_name ? `· ${item.subject_name}` : ""}</p>
                    <p className="mt-1 text-sm text-slate-500">Due: {formatDate(item.due_date)} {item.teacher_name ? `· ${item.teacher_name}` : ""}</p>
                  </div>
                  <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusClass(item.submission_status)}`}>{item.submission_status}</span>
                </div>
                {item.description && <p className="mt-3 text-sm text-slate-600">{item.description}</p>}
                <div className="mt-3 flex flex-wrap gap-3">
                  {item.attachment_url && <a href={fileUrl(item.attachment_url)} target="_blank" className="inline-flex items-center gap-2 text-sm font-semibold text-slate-900 underline underline-offset-4"><FileText size={16} /> Homework file</a>}
                  {item.submission_attachment_url && <a href={fileUrl(item.submission_attachment_url)} target="_blank" className="inline-flex items-center gap-2 text-sm font-semibold text-slate-900 underline underline-offset-4"><FileText size={16} /> Submitted file</a>}
                </div>
                {item.teacher_feedback && <p className="mt-3 rounded-xl bg-green-50 px-3 py-2 text-sm text-green-700"><span className="font-semibold">Teacher feedback:</span> {item.teacher_feedback}</p>}
              </div>
            ))}
          </div>
        )}
      </Card>
    </AppSection>
  );
}

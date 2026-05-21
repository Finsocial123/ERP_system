"use client";

import { useEffect, useMemo, useState } from "react";
import { FileText, RefreshCcw, Send, UploadCloud } from "lucide-react";

import { AppSection } from "@/components/CrudManager";
import { Button, Card, Label, Textarea } from "@/components/ui";
import { apiFetch, apiUpload, fileUrl } from "@/lib/api";
import type { StudentHomework as StudentHomeworkType } from "@/types";

function statusClass(status: string) {
  if (status === "CHECKED") return "bg-green-50 text-green-700";
  if (status === "SUBMITTED") return "bg-blue-50 text-blue-700";
  return "bg-amber-50 text-amber-700";
}

function formatDate(value?: string | null) {
  if (!value) return "-";
  return new Date(value).toLocaleDateString();
}

export default function StudentHomework() {
  const [homework, setHomework] = useState<StudentHomeworkType[]>([]);
  const [selected, setSelected] = useState<StudentHomeworkType | null>(null);
  const [answerText, setAnswerText] = useState("");
  const [attachment, setAttachment] = useState<File | null>(null);
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const loadHomework = async () => {
    setLoading(true);
    setError("");
    try {
      const rows = await apiFetch<StudentHomeworkType[]>("/homework/student/assignments");
      setHomework(rows);
      if (selected) {
        const refreshed = rows.find((item) => item.id === selected.id) || null;
        setSelected(refreshed);
        setAnswerText(refreshed?.answer_text || "");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load homework");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadHomework();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const counts = useMemo(() => {
    return homework.reduce(
      (acc, item) => {
        acc.total += 1;
        if (item.submission_status === "PENDING") acc.pending += 1;
        if (item.submission_status === "SUBMITTED") acc.submitted += 1;
        if (item.submission_status === "CHECKED") acc.checked += 1;
        return acc;
      },
      { total: 0, pending: 0, submitted: 0, checked: 0 }
    );
  }, [homework]);

  const visibleHomework = homework.filter((item) => statusFilter === "ALL" || item.submission_status === statusFilter);

  const openSubmit = (item: StudentHomeworkType) => {
    setSelected(item);
    setAnswerText(item.answer_text || "");
    setAttachment(null);
    setSuccess("");
    setError("");
  };

  const submitHomework = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!selected) return;
    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      const data = new FormData();
      data.append("answer_text", answerText);
      if (attachment) data.append("attachment", attachment);
      const updated = await apiUpload<StudentHomeworkType>(`/homework/assignments/${selected.id}/submit`, data, { method: "POST" });
      setSelected(updated);
      setSuccess("Homework submitted successfully");
      setAttachment(null);
      await loadHomework();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit homework");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AppSection title="My Homework" description="View homework assigned to your class and submit your answer with optional PDF/image work.">
      <div className="mb-6 grid gap-4 md:grid-cols-4">
        <Card><p className="text-sm text-slate-500">Total</p><p className="mt-2 text-3xl font-bold text-slate-900">{counts.total}</p></Card>
        <Card><p className="text-sm text-slate-500">Pending</p><p className="mt-2 text-3xl font-bold text-amber-700">{counts.pending}</p></Card>
        <Card><p className="text-sm text-slate-500">Submitted</p><p className="mt-2 text-3xl font-bold text-blue-700">{counts.submitted}</p></Card>
        <Card><p className="text-sm text-slate-500">Checked</p><p className="mt-2 text-3xl font-bold text-green-700">{counts.checked}</p></Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <Card>
          <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <h2 className="text-lg font-bold text-slate-900">Assigned Homework</h2>
              <p className="text-sm text-slate-500">Open a homework to submit or resubmit before checking.</p>
            </div>
            <div className="flex gap-2">
              <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm outline-none">
                <option value="ALL">All</option>
                <option value="PENDING">Pending</option>
                <option value="SUBMITTED">Submitted</option>
                <option value="CHECKED">Checked</option>
              </select>
              <button type="button" onClick={loadHomework} className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"><RefreshCcw size={16} /> Refresh</button>
            </div>
          </div>

          {error && <p className="mb-4 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
          {loading ? <p className="text-sm text-slate-500">Loading homework...</p> : visibleHomework.length === 0 ? <p className="text-sm text-slate-500">No homework found.</p> : (
            <div className="space-y-3">
              {visibleHomework.map((item) => (
                <div key={item.id} className={`rounded-2xl border p-4 ${selected?.id === item.id ? "border-slate-900 bg-slate-50" : "border-slate-200 bg-white"}`}>
                  <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                    <div>
                      <h3 className="font-bold text-slate-900">{item.title}</h3>
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
                  <button type="button" onClick={() => openSubmit(item)} className="mt-4 inline-flex items-center gap-2 rounded-xl bg-slate-900 px-3 py-2 text-sm font-semibold text-white hover:bg-slate-700"><Send size={16} /> {item.submission_status === "PENDING" ? "Submit" : "Resubmit"}</button>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card>
          <h2 className="text-lg font-bold text-slate-900">Submit Homework</h2>
          {!selected ? <p className="mt-2 text-sm text-slate-500">Select a homework from the list to submit your answer.</p> : (
            <form onSubmit={submitHomework} className="mt-4 space-y-4">
              <div className="rounded-xl bg-slate-50 p-4">
                <p className="font-semibold text-slate-900">{selected.title}</p>
                <p className="mt-1 text-sm text-slate-500">Due: {formatDate(selected.due_date)}</p>
              </div>
              <div>
                <Label>Answer / Notes</Label>
                <Textarea value={answerText} onChange={(e) => setAnswerText(e.target.value)} placeholder="Write your answer or notes here..." />
              </div>
              <div>
                <Label>PDF / Image Upload</Label>
                <label className="flex cursor-pointer items-center justify-between rounded-xl border border-dashed border-slate-300 bg-slate-50 px-4 py-3 text-sm text-slate-600 hover:bg-slate-100">
                  <span className="inline-flex items-center gap-2"><UploadCloud size={18} /> {attachment ? attachment.name : "Choose PDF or image"}</span>
                  <input className="hidden" type="file" accept="application/pdf,image/*" onChange={(e) => setAttachment(e.target.files?.[0] || null)} />
                </label>
              </div>
              {success && <p className="rounded-xl bg-green-50 px-3 py-2 text-sm text-green-700">{success}</p>}
              <Button type="submit" disabled={submitting}>{submitting ? "Submitting..." : "Submit Homework"}</Button>
            </form>
          )}
        </Card>
      </div>
    </AppSection>
  );
}

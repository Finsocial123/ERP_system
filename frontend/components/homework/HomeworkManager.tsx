"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { CheckCircle2, Edit2, Eye, FileText, Plus, RefreshCcw, Search, Trash2, UploadCloud, X } from "lucide-react";

import { AppSection } from "@/components/CrudManager";
import { Button, Card, Input, Label, Textarea } from "@/components/ui";
import { apiFetch, apiUpload, fileUrl } from "@/lib/api";
import type { HomeworkAssignment, HomeworkMeta, HomeworkSubmission } from "@/types";

type Props = {
  mode: "admin" | "teacher";
};

type FormState = {
  title: string;
  description: string;
  due_date: string;
  class_id: string;
  section_id: string;
  subject_id: string;
  teacher_id: string;
  attachment: File | null;
};

const emptyForm: FormState = {
  title: "",
  description: "",
  due_date: "",
  class_id: "",
  section_id: "",
  subject_id: "",
  teacher_id: "",
  attachment: null,
};

function SelectBox({ value, onChange, children, required = false }: { value: string; onChange: (value: string) => void; children: React.ReactNode; required?: boolean }) {
  return (
    <select
      value={value}
      onChange={(event) => onChange(event.target.value)}
      required={required}
      className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm outline-none transition focus:border-slate-400"
    >
      {children}
    </select>
  );
}

function statusClass(status: string) {
  if (status === "CHECKED") return "bg-green-50 text-green-700";
  if (status === "SUBMITTED") return "bg-blue-50 text-blue-700";
  return "bg-amber-50 text-amber-700";
}

function formatDate(value?: string | null) {
  if (!value) return "-";
  return new Date(value).toLocaleDateString();
}

export default function HomeworkManager({ mode }: Props) {
  const [meta, setMeta] = useState<HomeworkMeta | null>(null);
  const [assignments, setAssignments] = useState<HomeworkAssignment[]>([]);
  const [submissions, setSubmissions] = useState<HomeworkSubmission[]>([]);
  const [form, setForm] = useState<FormState>(emptyForm);
  const [editing, setEditing] = useState<HomeworkAssignment | null>(null);
  const [selected, setSelected] = useState<HomeworkAssignment | null>(null);
  const [feedback, setFeedback] = useState<Record<number, string>>({});
  const [search, setSearch] = useState("");
  const [classFilter, setClassFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const submissionsRef = useRef<HTMLDivElement | null>(null);

  const filteredSections = useMemo(() => {
    if (!meta) return [];
    const classId = form.class_id;
    if (!classId) return meta.sections;
    return meta.sections.filter((section) => section.extra === classId);
  }, [form.class_id, meta]);

  const filteredSubjects = useMemo(() => {
    if (!meta || !form.class_id) return [];
    return meta.subjects.filter((subject) => subject.extra === form.class_id);
  }, [form.class_id, meta]);

  const sectionIdForName = (classId?: number | null, sectionName?: string | null) => {
    if (!meta || !classId || !sectionName) return null;
    const match = meta.sections.find((item) => item.extra === String(classId) && item.name.trim().toLowerCase() === sectionName.trim().toLowerCase());
    return match?.id ?? null;
  };

  const loadData = async () => {
    setLoading(true);
    setError("");
    try {
      const [metaData, homeworkData] = await Promise.all([
        apiFetch<HomeworkMeta>("/homework/meta"),
        apiFetch<HomeworkAssignment[]>(`/homework/assignments${classFilter ? `?class_id=${classFilter}` : ""}`),
      ]);
      setMeta(metaData);
      setAssignments(homeworkData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load homework");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [classFilter]);

  const loadSubmissions = async (assignment: HomeworkAssignment) => {
    setSelected(assignment);
    setError("");
    try {
      const rows = await apiFetch<HomeworkSubmission[]>(`/homework/assignments/${assignment.id}/submissions`);
      setSubmissions(rows);
      const nextFeedback: Record<number, string> = {};
      rows.forEach((row) => {
        if (row.id) nextFeedback[row.id] = row.teacher_feedback || "";
      });
      setFeedback(nextFeedback);
      window.setTimeout(() => {
        submissionsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 80);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load submissions");
    }
  };

  const update = (key: keyof FormState, value: string | File | null) => {
    setForm((prev) => ({
      ...prev,
      [key]: value,
      ...(key === "class_id" ? { section_id: "", subject_id: "" } : {}),
    } as FormState));
  };

  const resetForm = () => {
    setForm(emptyForm);
    setEditing(null);
  };

  const startEdit = (item: HomeworkAssignment) => {
    setEditing(item);
    setForm({
      title: item.title,
      description: item.description || "",
      due_date: item.due_date,
      class_id: String(item.class_id),
      section_id: item.section_name ? String(sectionIdForName(item.class_id, item.section_name) ?? "") : item.section_id ? String(item.section_id) : "",
      subject_id: item.subject_id ? String(item.subject_id) : "",
      teacher_id: item.teacher_id ? String(item.teacher_id) : "",
      attachment: null,
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const buildFormData = () => {
    const data = new FormData();
    data.append("title", form.title.trim());
    data.append("description", form.description.trim());
    data.append("due_date", form.due_date);
    data.append("class_id", form.class_id);
    if (form.section_id) data.append("section_id", form.section_id);
    if (form.subject_id) data.append("subject_id", form.subject_id);
    if (mode === "admin" && form.teacher_id) data.append("teacher_id", form.teacher_id);
    if (form.attachment) data.append("attachment", form.attachment);
    return data;
  };

  const saveAssignment = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const path = editing ? `/homework/assignments/${editing.id}` : "/homework/assignments";
      await apiUpload<HomeworkAssignment>(path, buildFormData(), { method: editing ? "PUT" : "POST" });
      setSuccess(editing ? "Homework updated successfully" : "Homework assigned successfully");
      resetForm();
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save homework");
    } finally {
      setSaving(false);
    }
  };

  const deleteAssignment = async (item: HomeworkAssignment) => {
    if (!confirm("Delete this homework assignment?")) return;
    setError("");
    try {
      await apiFetch(`/homework/assignments/${item.id}`, { method: "DELETE" });
      if (selected?.id === item.id) {
        setSelected(null);
        setSubmissions([]);
      }
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete homework");
    }
  };

  const checkSubmission = async (row: HomeworkSubmission) => {
    if (!row.id) return;
    setError("");
    try {
      await apiFetch(`/homework/submissions/${row.id}/check`, {
        method: "PATCH",
        body: JSON.stringify({ teacher_feedback: feedback[row.id] || "" }),
      });
      if (selected) await loadSubmissions(selected);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to check submission");
    }
  };

  const visibleAssignments = assignments.filter((item) => {
    if (!search.trim()) return true;
    const query = search.toLowerCase();
    return [item.title, item.description, item.class_name, item.section_name, item.subject_name, item.teacher_name]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(query));
  });

  return (
    <AppSection
      title={mode === "teacher" ? "Homework & Assignment" : "Homework Monitor"}
      description={mode === "teacher" ? "Create homework, upload PDF/image work, view submissions and mark them checked." : "View and manage all homework assigned in the school."}
    >
      <div className="grid gap-6 xl:grid-cols-[1fr_1.1fr]">
        <Card>
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-bold text-slate-900">{editing ? "Edit Homework" : "Assign Homework"}</h2>
              <p className="text-sm text-slate-500">PDF and image attachments are supported up to 10 MB.</p>
            </div>
            {editing && (
              <button type="button" onClick={resetForm} className="rounded-xl border border-slate-200 p-2 text-slate-600 hover:bg-slate-100">
                <X size={18} />
              </button>
            )}
          </div>

          <form onSubmit={saveAssignment} className="grid gap-4 md:grid-cols-2">
            <div className="md:col-span-2"><Label>Homework Title</Label><Input value={form.title} onChange={(e) => update("title", e.target.value)} required placeholder="Chapter 4 worksheet" /></div>
            <div><Label>Class</Label><SelectBox value={form.class_id} onChange={(value) => update("class_id", value)} required><option value="">Select class</option>{meta?.classes.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</SelectBox></div>
            <div><Label>Section</Label><SelectBox value={form.section_id} onChange={(value) => update("section_id", value)}><option value="">All sections</option>{filteredSections.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</SelectBox></div>
            <div><Label>Subject</Label><SelectBox value={form.subject_id} onChange={(value) => update("subject_id", value)}><option value="">{form.class_id ? "Optional subject" : "Select class first"}</option>{filteredSubjects.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</SelectBox></div>
            <div><Label>Due Date</Label><Input type="date" value={form.due_date} onChange={(e) => update("due_date", e.target.value)} required /></div>
            {mode === "admin" && (
              <div className="md:col-span-2"><Label>Teacher</Label><SelectBox value={form.teacher_id} onChange={(value) => update("teacher_id", value)}><option value="">No teacher selected</option>{meta?.teachers.map((item) => <option key={item.id} value={item.id}>{item.name} {item.extra ? `(${item.extra})` : ""}</option>)}</SelectBox></div>
            )}
            <div className="md:col-span-2"><Label>Description</Label><Textarea value={form.description} onChange={(e) => update("description", e.target.value)} placeholder="Write homework instructions here..." /></div>
            <div className="md:col-span-2">
              <Label>PDF / Image Upload</Label>
              <label className="flex cursor-pointer items-center justify-between rounded-xl border border-dashed border-slate-300 bg-slate-50 px-4 py-3 text-sm text-slate-600 hover:bg-slate-100">
                <span className="inline-flex items-center gap-2"><UploadCloud size={18} /> {form.attachment ? form.attachment.name : "Choose PDF or image"}</span>
                <input className="hidden" type="file" accept="application/pdf,image/*" onChange={(e) => update("attachment", e.target.files?.[0] || null)} />
              </label>
            </div>
            <div className="flex items-center gap-2 md:col-span-2">
              <Button type="submit" disabled={saving}>{saving ? "Saving..." : <span className="inline-flex items-center gap-2"><Plus size={16} /> {editing ? "Update Homework" : "Assign Homework"}</span>}</Button>
              <button type="button" onClick={loadData} className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"><RefreshCcw size={16} /> Refresh</button>
            </div>
          </form>

          {error && <p className="mt-4 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
          {success && <p className="mt-4 rounded-xl bg-green-50 px-3 py-2 text-sm text-green-700">{success}</p>}
        </Card>

        <Card>
          <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
            <div>
              <h2 className="text-lg font-bold text-slate-900">Homework List</h2>
              <p className="text-sm text-slate-500">Open an item to review pending, submitted and checked work.</p>
            </div>
            <div className="flex gap-2">
              <div className="relative"><Search className="absolute left-3 top-2.5 text-slate-400" size={16} /><Input className="pl-9" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search homework" /></div>
              <SelectBox value={classFilter} onChange={setClassFilter}><option value="">All classes</option>{meta?.classes.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</SelectBox>
            </div>
          </div>

          {loading ? <p className="text-sm text-slate-500">Loading homework...</p> : visibleAssignments.length === 0 ? <p className="text-sm text-slate-500">No homework assigned yet.</p> : (
            <div className="space-y-3">
              {visibleAssignments.map((item) => (
                <div key={item.id} className={`rounded-2xl border p-4 ${selected?.id === item.id ? "border-slate-900 bg-slate-50" : "border-slate-200 bg-white"}`}>
                  <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                    <div>
                      <h3 className="font-bold text-slate-900">{item.title}</h3>
                      <p className="mt-1 text-sm text-slate-500">{item.class_name || `Class ${item.class_id}`} {item.section_name ? `- ${item.section_name}` : "· All sections"} {item.subject_name ? `· ${item.subject_name}` : ""}</p>
                      <p className="mt-1 text-sm text-slate-500">Due: {formatDate(item.due_date)} {item.teacher_name ? `· Teacher: ${item.teacher_name}` : ""}</p>
                      {item.attachment_url && <a href={fileUrl(item.attachment_url)} target="_blank" className="mt-2 inline-flex items-center gap-2 text-sm font-semibold text-slate-900 underline underline-offset-4"><FileText size={16} /> {item.attachment_filename || "Open attachment"}</a>}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <span className="rounded-full bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700">Pending {item.stats.pending}</span>
                      <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">Submitted {item.stats.submitted}</span>
                      <span className="rounded-full bg-green-50 px-3 py-1 text-xs font-semibold text-green-700">Checked {item.stats.checked}</span>
                    </div>
                  </div>
                  {item.description && <p className="mt-3 text-sm text-slate-600">{item.description}</p>}
                  <div className="mt-4 flex flex-wrap gap-2">
                    <button type="button" onClick={() => loadSubmissions(item)} className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"><Eye size={16} /> Submissions</button>
                    <button type="button" onClick={() => startEdit(item)} className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"><Edit2 size={16} /> Edit</button>
                    <button type="button" onClick={() => deleteAssignment(item)} className="inline-flex items-center gap-2 rounded-xl border border-red-100 px-3 py-2 text-sm font-semibold text-red-700 hover:bg-red-50"><Trash2 size={16} /> Delete</button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {selected && (
        <div ref={submissionsRef}>
          <Card className="mt-6">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-bold text-slate-900">Submissions: {selected.title}</h2>
              <p className="text-sm text-slate-500">Pending means the student has not submitted yet. Submitted can be marked as checked.</p>
            </div>
            <button type="button" onClick={() => { setSelected(null); setSubmissions([]); }} className="rounded-xl border border-slate-200 p-2 text-slate-600 hover:bg-slate-100"><X size={18} /></button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-100 text-xs uppercase text-slate-500">
                <tr><th className="p-3">Student</th><th className="p-3">Status</th><th className="p-3">Answer</th><th className="p-3">Attachment</th><th className="p-3">Feedback</th><th className="p-3">Action</th></tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {submissions.map((row) => (
                  <tr key={`${row.student_id}-${row.id || "pending"}`}>
                    <td className="p-3"><p className="font-semibold text-slate-900">{row.student_name}</p><p className="text-xs text-slate-500">{row.admission_no} {row.roll_number ? `· Roll ${row.roll_number}` : ""}</p></td>
                    <td className="p-3"><span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusClass(row.status)}`}>{row.status}</span></td>
                    <td className="max-w-sm p-3 text-slate-600">{row.answer_text || "-"}</td>
                    <td className="p-3">{row.attachment_url ? <a href={fileUrl(row.attachment_url)} target="_blank" className="font-semibold text-slate-900 underline underline-offset-4">Open file</a> : "-"}</td>
                    <td className="p-3"><Textarea value={row.id ? feedback[row.id] || "" : ""} disabled={!row.id} onChange={(e) => row.id && setFeedback((prev) => ({ ...prev, [row.id as number]: e.target.value }))} placeholder="Feedback" className="min-h-16" /></td>
                    <td className="p-3">{row.id ? <button type="button" onClick={() => checkSubmission(row)} className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-3 py-2 text-sm font-semibold text-white hover:bg-slate-700"><CheckCircle2 size={16} /> Mark Checked</button> : <span className="text-xs text-slate-500">Waiting</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          </Card>
        </div>
      )}
    </AppSection>
  );
}

"use client";

import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, Edit2, Eye, Plus, RefreshCcw, Save, Search, Trash2, X } from "lucide-react";

import { AppSection } from "@/components/CrudManager";
import { Button, Card, Input, Label, Textarea } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import type { ClassResult, Exam, ExamMark, ExamMeta, ExamSubject, SubjectResult } from "@/types";

type ExamForm = {
  name: string;
  exam_type: string;
  description: string;
  class_id: string;
  section_id: string;
  academic_session_id: string;
  start_date: string;
  end_date: string;
};

type SubjectForm = {
  subject_id: string;
  teacher_id: string;
  max_marks: string;
  pass_marks: string;
  exam_date: string;
};

type MarkDraft = {
  student_id: number;
  marks_obtained: string;
  is_absent: boolean;
  remarks: string;
};

const emptyExam: ExamForm = {
  name: "",
  exam_type: "",
  description: "",
  class_id: "",
  section_id: "",
  academic_session_id: "",
  start_date: "",
  end_date: "",
};

const emptySubject: SubjectForm = {
  subject_id: "",
  teacher_id: "",
  max_marks: "100",
  pass_marks: "33",
  exam_date: "",
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
  if (status === "PASS" || status === "PUBLISHED") return "bg-emerald-50 text-emerald-700";
  if (status === "FAIL" || status === "ABSENT") return "bg-red-50 text-red-700";
  return "bg-amber-50 text-amber-700";
}

function displayDate(value?: string | null) {
  if (!value) return "-";
  return value.slice(0, 10);
}

function numberOrNull(value: string) {
  if (value.trim() === "") return null;
  return Number(value);
}

export default function ExamManager({ mode = "admin" }: { mode?: "admin" | "teacher" }) {
  const [tab, setTab] = useState<"exams" | "subjects" | "marks" | "reports">("exams");
  const [meta, setMeta] = useState<ExamMeta | null>(null);
  const [exams, setExams] = useState<Exam[]>([]);
  const [selectedExamId, setSelectedExamId] = useState("");
  const [examSubjects, setExamSubjects] = useState<ExamSubject[]>([]);
  const [selectedSubjectId, setSelectedSubjectId] = useState("");
  const [marks, setMarks] = useState<ExamMark[]>([]);
  const [markDrafts, setMarkDrafts] = useState<Record<number, MarkDraft>>({});
  const [classResult, setClassResult] = useState<ClassResult | null>(null);
  const [subjectResult, setSubjectResult] = useState<SubjectResult | null>(null);
  const [examForm, setExamForm] = useState<ExamForm>(emptyExam);
  const [subjectForm, setSubjectForm] = useState<SubjectForm>(emptySubject);
  const [editingExam, setEditingExam] = useState<Exam | null>(null);
  const [editingSubject, setEditingSubject] = useState<ExamSubject | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const selectedExam = useMemo(() => exams.find((item) => String(item.id) === selectedExamId) || null, [exams, selectedExamId]);
  const selectedSubject = useMemo(() => examSubjects.find((item) => String(item.id) === selectedSubjectId) || null, [examSubjects, selectedSubjectId]);

  const filteredSections = useMemo(() => {
    if (!meta) return [];
    if (!examForm.class_id) return meta.sections;
    return meta.sections.filter((item) => item.extra === examForm.class_id);
  }, [examForm.class_id, meta]);

  const filteredSubjects = useMemo(() => {
    if (!meta) return [];
    const examClass = selectedExam?.class_id ? String(selectedExam.class_id) : examForm.class_id;
    if (!examClass) return meta.subjects;
    return meta.subjects.filter((item) => !item.extra || item.extra === examClass);
  }, [examForm.class_id, meta, selectedExam?.class_id]);

  const loadData = async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      if (search.trim()) params.set("q", search.trim());
      if (statusFilter) params.set("status", statusFilter);
      const [metaData, examData] = await Promise.all([
        apiFetch<ExamMeta>("/exams/meta"),
        apiFetch<Exam[]>(`/exams${params.toString() ? `?${params.toString()}` : ""}`),
      ]);
      setMeta(metaData);
      setExams(examData);
      setExamForm((prev) => ({ ...prev, academic_session_id: prev.academic_session_id || String(metaData.current_academic_session_id || "") }));
      if (!selectedExamId && examData.length) setSelectedExamId(String(examData[0].id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load exams");
    } finally {
      setLoading(false);
    }
  };

  const loadSubjects = async (examId: string) => {
    if (!examId) {
      setExamSubjects([]);
      setSelectedSubjectId("");
      return;
    }
    try {
      const data = await apiFetch<ExamSubject[]>(`/exams/${examId}/subjects`);
      setExamSubjects(data);
      if (!selectedSubjectId && data.length) setSelectedSubjectId(String(data[0].id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load exam subjects");
    }
  };

  const loadMarks = async () => {
    if (!selectedExamId || !selectedSubjectId) {
      setMarks([]);
      setMarkDrafts({});
      return;
    }
    try {
      const data = await apiFetch<ExamMark[]>(`/exams/${selectedExamId}/marks?exam_subject_id=${selectedSubjectId}`);
      setMarks(data);
      const drafts: Record<number, MarkDraft> = {};
      data.forEach((item) => {
        drafts[item.student_id] = {
          student_id: item.student_id,
          marks_obtained: item.marks_obtained === null || item.marks_obtained === undefined ? "" : String(item.marks_obtained),
          is_absent: Boolean(item.is_absent),
          remarks: item.remarks || "",
        };
      });
      setMarkDrafts(drafts);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load marks");
    }
  };

  const loadReports = async () => {
    if (!selectedExamId) {
      setClassResult(null);
      setSubjectResult(null);
      return;
    }
    try {
      const classData = await apiFetch<ClassResult>(`/exams/${selectedExamId}/class-result`);
      setClassResult(classData);
      if (selectedSubjectId) {
        const subjectData = await apiFetch<SubjectResult>(`/exams/${selectedExamId}/subject-result/${selectedSubjectId}`);
        setSubjectResult(subjectData);
      } else {
        setSubjectResult(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load reports");
    }
  };

  useEffect(() => {
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    loadSubjects(selectedExamId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedExamId]);

  useEffect(() => {
    if (tab === "marks") loadMarks();
    if (tab === "reports") loadReports();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, selectedExamId, selectedSubjectId]);

  const resetExam = () => {
    setExamForm({ ...emptyExam, academic_session_id: String(meta?.current_academic_session_id || "") });
    setEditingExam(null);
  };

  const resetSubject = () => {
    setSubjectForm(emptySubject);
    setEditingSubject(null);
  };

  const saveExam = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    setSuccess("");
    const payload = {
      name: examForm.name.trim(),
      exam_type: examForm.exam_type.trim() || null,
      description: examForm.description.trim() || null,
      class_id: Number(examForm.class_id),
      section_id: examForm.section_id ? Number(examForm.section_id) : null,
      academic_session_id: examForm.academic_session_id ? Number(examForm.academic_session_id) : null,
      start_date: examForm.start_date || null,
      end_date: examForm.end_date || null,
    };
    try {
      const saved = await apiFetch<Exam>(editingExam ? `/exams/${editingExam.id}` : "/exams", {
        method: editingExam ? "PUT" : "POST",
        body: JSON.stringify(payload),
      });
      setSuccess(editingExam ? "Exam updated successfully" : "Exam created successfully");
      setSelectedExamId(String(saved.id));
      resetExam();
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save exam");
    } finally {
      setSaving(false);
    }
  };

  const editExam = (exam: Exam) => {
    setEditingExam(exam);
    setExamForm({
      name: exam.name,
      exam_type: exam.exam_type || "",
      description: exam.description || "",
      class_id: String(exam.class_id),
      section_id: exam.section_id ? String(exam.section_id) : "",
      academic_session_id: exam.academic_session_id ? String(exam.academic_session_id) : "",
      start_date: exam.start_date || "",
      end_date: exam.end_date || "",
    });
    setTab("exams");
  };

  const deleteExam = async (exam: Exam) => {
    if (!confirm(`Delete exam ${exam.name}?`)) return;
    setError("");
    setSuccess("");
    try {
      await apiFetch(`/exams/${exam.id}`, { method: "DELETE" });
      if (selectedExamId === String(exam.id)) setSelectedExamId("");
      setSuccess("Exam deleted successfully");
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete exam");
    }
  };

  const publishToggle = async (exam: Exam) => {
    setError("");
    setSuccess("");
    try {
      const action = exam.result_status === "PUBLISHED" ? "unpublish" : "publish";
      await apiFetch(`/exams/${exam.id}/${action}`, { method: "POST" });
      setSuccess(action === "publish" ? "Result published successfully" : "Result moved back to draft");
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update result status");
    }
  };

  const saveSubject = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!selectedExamId) {
      setError("Select an exam first");
      return;
    }
    setSaving(true);
    setError("");
    setSuccess("");
    const payload = {
      subject_id: Number(subjectForm.subject_id),
      teacher_id: subjectForm.teacher_id ? Number(subjectForm.teacher_id) : null,
      max_marks: Number(subjectForm.max_marks),
      pass_marks: Number(subjectForm.pass_marks),
      exam_date: subjectForm.exam_date || null,
    };
    try {
      const saved = await apiFetch<ExamSubject>(editingSubject ? `/exams/${selectedExamId}/subjects/${editingSubject.id}` : `/exams/${selectedExamId}/subjects`, {
        method: editingSubject ? "PUT" : "POST",
        body: JSON.stringify(payload),
      });
      setSelectedSubjectId(String(saved.id));
      setSuccess(editingSubject ? "Exam subject updated successfully" : "Exam subject added successfully");
      resetSubject();
      await loadSubjects(selectedExamId);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save exam subject");
    } finally {
      setSaving(false);
    }
  };

  const editSubject = (subject: ExamSubject) => {
    setEditingSubject(subject);
    setSubjectForm({
      subject_id: String(subject.subject_id),
      teacher_id: subject.teacher_id ? String(subject.teacher_id) : "",
      max_marks: String(subject.max_marks),
      pass_marks: String(subject.pass_marks),
      exam_date: subject.exam_date || "",
    });
    setTab("subjects");
  };

  const deleteSubject = async (subject: ExamSubject) => {
    if (!selectedExamId || !confirm(`Remove ${subject.subject_name || "subject"} from this exam?`)) return;
    setError("");
    setSuccess("");
    try {
      await apiFetch(`/exams/${selectedExamId}/subjects/${subject.id}`, { method: "DELETE" });
      if (selectedSubjectId === String(subject.id)) setSelectedSubjectId("");
      setSuccess("Exam subject removed successfully");
      await loadSubjects(selectedExamId);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to remove subject");
    }
  };

  const saveMarks = async () => {
    if (!selectedExamId || !selectedSubjectId) return;
    setSaving(true);
    setError("");
    setSuccess("");
    const payload = {
      exam_subject_id: Number(selectedSubjectId),
      marks: Object.values(markDrafts).map((draft) => ({
        student_id: draft.student_id,
        marks_obtained: draft.is_absent ? null : numberOrNull(draft.marks_obtained),
        is_absent: draft.is_absent,
        remarks: draft.remarks.trim() || null,
      })),
    };
    try {
      await apiFetch(`/exams/${selectedExamId}/marks/bulk`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setSuccess("Marks saved successfully");
      await loadMarks();
      await loadReports();
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save marks");
    } finally {
      setSaving(false);
    }
  };

  const updateDraft = (studentId: number, changes: Partial<MarkDraft>) => {
    setMarkDrafts((prev) => ({
      ...prev,
      [studentId]: { ...prev[studentId], student_id: studentId, ...changes },
    }));
  };

  const applySearch = async (event: React.FormEvent) => {
    event.preventDefault();
    await loadData();
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-3 md:flex-row md:items-center">
        <div>
          <p className="text-sm font-semibold uppercase tracking-wide text-slate-400">Phase 8</p>
          <h1 className="text-2xl font-bold text-slate-900">Exam and Result Management</h1>
          <p className="text-sm text-slate-500">Create exams, add subjects, enter marks, publish results and view class/subject reports.</p>
        </div>
        <Button onClick={loadData} disabled={loading} className="flex items-center gap-2">
          <RefreshCcw size={16} /> Refresh
        </Button>
      </div>

      {error && <div className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</div>}
      {success && <div className="rounded-xl bg-emerald-50 p-3 text-sm text-emerald-700">{success}</div>}

      <div className="flex flex-wrap gap-2">
        {[
          ["exams", "Create Exam"],
          ["subjects", "Exam Subjects"],
          ["marks", "Marks Entry"],
          ["reports", "Reports"],
        ].map(([value, label]) => (
          <button
            key={value}
            type="button"
            onClick={() => setTab(value as typeof tab)}
            className={`rounded-xl px-4 py-2 text-sm font-semibold ${tab === value ? "bg-slate-900 text-white" : "border border-slate-200 bg-white text-slate-700"}`}
          >
            {label}
          </button>
        ))}
      </div>

      {loading && <Card>Loading exam module...</Card>}

      {!loading && tab === "exams" && (
        <div className="grid gap-6 xl:grid-cols-[420px_1fr]">
          <AppSection title={editingExam ? "Edit exam" : "Create exam"} description="Choose class, optional section, dates and academic session.">
            <form onSubmit={saveExam} className="space-y-4">
              <div>
                <Label>Exam Name</Label>
                <Input value={examForm.name} onChange={(event) => setExamForm({ ...examForm, name: event.target.value })} placeholder="Mid Term Exam" required />
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <Label>Exam Type</Label>
                  <Input value={examForm.exam_type} onChange={(event) => setExamForm({ ...examForm, exam_type: event.target.value })} placeholder="Term / Unit Test" />
                </div>
                <div>
                  <Label>Academic Session</Label>
                  <SelectBox value={examForm.academic_session_id} onChange={(value) => setExamForm({ ...examForm, academic_session_id: value })}>
                    <option value="">Latest / Current</option>
                    {meta?.academic_sessions.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                  </SelectBox>
                </div>
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <Label>Class</Label>
                  <SelectBox value={examForm.class_id} onChange={(value) => setExamForm({ ...examForm, class_id: value, section_id: "" })} required>
                    <option value="">Select class</option>
                    {meta?.classes.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                  </SelectBox>
                </div>
                <div>
                  <Label>Section</Label>
                  <SelectBox value={examForm.section_id} onChange={(value) => setExamForm({ ...examForm, section_id: value })}>
                    <option value="">All sections</option>
                    {filteredSections.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                  </SelectBox>
                </div>
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <Label>Start Date</Label>
                  <Input type="date" value={examForm.start_date} onChange={(event) => setExamForm({ ...examForm, start_date: event.target.value })} />
                </div>
                <div>
                  <Label>End Date</Label>
                  <Input type="date" value={examForm.end_date} onChange={(event) => setExamForm({ ...examForm, end_date: event.target.value })} />
                </div>
              </div>
              <div>
                <Label>Description</Label>
                <Textarea value={examForm.description} onChange={(event) => setExamForm({ ...examForm, description: event.target.value })} placeholder="Optional exam instructions" />
              </div>
              <div className="flex flex-wrap gap-2">
                <Button disabled={saving} className="flex items-center gap-2"><Plus size={16} /> {editingExam ? "Update Exam" : "Create Exam"}</Button>
                {editingExam && <button type="button" onClick={resetExam} className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700">Cancel</button>}
              </div>
            </form>
          </AppSection>

          <AppSection title="Exam list" description="Search, select, edit, publish or delete exams.">
            <form onSubmit={applySearch} className="mb-4 grid gap-3 md:grid-cols-[1fr_180px_auto]">
              <div className="relative">
                <Search className="absolute left-3 top-2.5 text-slate-400" size={16} />
                <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search exam name/type" className="pl-9" />
              </div>
              <SelectBox value={statusFilter} onChange={setStatusFilter}>
                <option value="">All status</option>
                <option value="DRAFT">Draft</option>
                <option value="PUBLISHED">Published</option>
              </SelectBox>
              <Button type="submit">Search</Button>
            </form>

            <div className="overflow-x-auto rounded-2xl border border-slate-200">
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <thead className="bg-slate-50 text-left text-slate-600">
                  <tr>
                    <th className="px-4 py-3">Exam</th>
                    <th className="px-4 py-3">Class</th>
                    <th className="px-4 py-3">Dates</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {exams.map((exam) => (
                    <tr key={exam.id} className={selectedExamId === String(exam.id) ? "bg-slate-50" : "bg-white"}>
                      <td className="px-4 py-3">
                        <button type="button" onClick={() => setSelectedExamId(String(exam.id))} className="font-semibold text-slate-900 hover:underline">{exam.name}</button>
                        <p className="text-xs text-slate-500">{exam.exam_type || "General"} · {exam.subjects_count} subjects · {exam.marks_entered_count} marks</p>
                      </td>
                      <td className="px-4 py-3 text-slate-600">{exam.class_name}{exam.section_name ? ` - ${exam.section_name}` : " · All sections"}</td>
                      <td className="px-4 py-3 text-slate-600">{displayDate(exam.start_date)} - {displayDate(exam.end_date)}</td>
                      <td className="px-4 py-3"><span className={`rounded-full px-2 py-1 text-xs font-semibold ${statusClass(exam.result_status)}`}>{exam.result_status}</span></td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-2">
                          <button type="button" onClick={() => editExam(exam)} className="rounded-lg border border-slate-200 p-2 text-slate-600"><Edit2 size={14} /></button>
                          <button type="button" onClick={() => publishToggle(exam)} className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700">{exam.result_status === "PUBLISHED" ? "Unpublish" : "Publish"}</button>
                          <button type="button" onClick={() => deleteExam(exam)} className="rounded-lg border border-red-100 p-2 text-red-600"><Trash2 size={14} /></button>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {exams.length === 0 && <tr><td colSpan={5} className="px-4 py-6 text-center text-slate-500">No exams found.</td></tr>}
                </tbody>
              </table>
            </div>
          </AppSection>
        </div>
      )}

      {!loading && tab === "subjects" && (
        <div className="grid gap-6 xl:grid-cols-[420px_1fr]">
          <AppSection title="Add exam subject" description="Attach subjects to the selected exam with max and pass marks.">
            <div className="mb-4">
              <Label>Selected Exam</Label>
              <SelectBox value={selectedExamId} onChange={setSelectedExamId} required>
                <option value="">Select exam</option>
                {exams.map((exam) => <option key={exam.id} value={exam.id}>{exam.name} · {exam.class_name}</option>)}
              </SelectBox>
            </div>
            <form onSubmit={saveSubject} className="space-y-4">
              <div>
                <Label>Subject</Label>
                <SelectBox value={subjectForm.subject_id} onChange={(value) => setSubjectForm({ ...subjectForm, subject_id: value })} required>
                  <option value="">Select subject</option>
                  {filteredSubjects.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                </SelectBox>
              </div>
              <div>
                <Label>Teacher / Examiner</Label>
                <SelectBox value={subjectForm.teacher_id} onChange={(value) => setSubjectForm({ ...subjectForm, teacher_id: value })}>
                  <option value="">Not assigned</option>
                  {meta?.teachers.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                </SelectBox>
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <Label>Max Marks</Label>
                  <Input type="number" min="1" value={subjectForm.max_marks} onChange={(event) => setSubjectForm({ ...subjectForm, max_marks: event.target.value })} required />
                </div>
                <div>
                  <Label>Pass Marks</Label>
                  <Input type="number" min="0" value={subjectForm.pass_marks} onChange={(event) => setSubjectForm({ ...subjectForm, pass_marks: event.target.value })} required />
                </div>
              </div>
              <div>
                <Label>Exam Date</Label>
                <Input type="date" value={subjectForm.exam_date} onChange={(event) => setSubjectForm({ ...subjectForm, exam_date: event.target.value })} />
              </div>
              <div className="flex flex-wrap gap-2">
                <Button disabled={saving || !selectedExamId} className="flex items-center gap-2"><Plus size={16} /> {editingSubject ? "Update Subject" : "Add Subject"}</Button>
                {editingSubject && <button type="button" onClick={resetSubject} className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700">Cancel</button>}
              </div>
            </form>
          </AppSection>

          <AppSection title="Exam subjects" description={selectedExam ? `${selectedExam.name} subjects` : "Select an exam to view subjects."}>
            <div className="overflow-x-auto rounded-2xl border border-slate-200">
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <thead className="bg-slate-50 text-left text-slate-600">
                  <tr>
                    <th className="px-4 py-3">Subject</th>
                    <th className="px-4 py-3">Teacher</th>
                    <th className="px-4 py-3">Marks</th>
                    <th className="px-4 py-3">Date</th>
                    <th className="px-4 py-3">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {examSubjects.map((subject) => (
                    <tr key={subject.id} className={selectedSubjectId === String(subject.id) ? "bg-slate-50" : "bg-white"}>
                      <td className="px-4 py-3"><button type="button" onClick={() => setSelectedSubjectId(String(subject.id))} className="font-semibold text-slate-900 hover:underline">{subject.subject_name}</button><p className="text-xs text-slate-500">{subject.marks_entered_count} marks entered</p></td>
                      <td className="px-4 py-3 text-slate-600">{subject.teacher_name || "-"}</td>
                      <td className="px-4 py-3 text-slate-600">Max {subject.max_marks} · Pass {subject.pass_marks}</td>
                      <td className="px-4 py-3 text-slate-600">{displayDate(subject.exam_date)}</td>
                      <td className="px-4 py-3">
                        <div className="flex gap-2">
                          <button type="button" onClick={() => editSubject(subject)} className="rounded-lg border border-slate-200 p-2 text-slate-600"><Edit2 size={14} /></button>
                          <button type="button" onClick={() => deleteSubject(subject)} className="rounded-lg border border-red-100 p-2 text-red-600"><Trash2 size={14} /></button>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {examSubjects.length === 0 && <tr><td colSpan={5} className="px-4 py-6 text-center text-slate-500">No subjects added for this exam.</td></tr>}
                </tbody>
              </table>
            </div>
          </AppSection>
        </div>
      )}

      {!loading && tab === "marks" && (
        <AppSection title="Marks entry" description="Enter marks for one exam subject. Grade and pass/fail status are calculated by backend.">
          <div className="mb-4 grid gap-3 md:grid-cols-2">
            <div>
              <Label>Exam</Label>
              <SelectBox value={selectedExamId} onChange={(value) => { setSelectedExamId(value); setSelectedSubjectId(""); }}>
                <option value="">Select exam</option>
                {exams.map((exam) => <option key={exam.id} value={exam.id}>{exam.name} · {exam.class_name}</option>)}
              </SelectBox>
            </div>
            <div>
              <Label>Subject</Label>
              <SelectBox value={selectedSubjectId} onChange={setSelectedSubjectId}>
                <option value="">Select subject</option>
                {examSubjects.map((subject) => <option key={subject.id} value={subject.id}>{subject.subject_name} · Max {subject.max_marks}</option>)}
              </SelectBox>
            </div>
          </div>

          {selectedSubject && <p className="mb-4 rounded-xl bg-slate-50 p-3 text-sm text-slate-600">Selected subject: <b>{selectedSubject.subject_name}</b> · Max marks: {selectedSubject.max_marks} · Pass marks: {selectedSubject.pass_marks}</p>}

          <div className="overflow-x-auto rounded-2xl border border-slate-200">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50 text-left text-slate-600">
                <tr>
                  <th className="px-4 py-3">Student</th>
                  <th className="px-4 py-3">Marks</th>
                  <th className="px-4 py-3">Absent</th>
                  <th className="px-4 py-3">Grade</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Remarks</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {marks.map((mark) => {
                  const draft = markDrafts[mark.student_id] || { student_id: mark.student_id, marks_obtained: "", is_absent: false, remarks: "" };
                  return (
                    <tr key={mark.student_id}>
                      <td className="px-4 py-3"><p className="font-semibold text-slate-900">{mark.student_name}</p><p className="text-xs text-slate-500">Adm: {mark.admission_no}{mark.roll_number ? ` · Roll: ${mark.roll_number}` : ""}</p></td>
                      <td className="px-4 py-3"><Input type="number" min="0" max={mark.max_marks} value={draft.marks_obtained} disabled={draft.is_absent} onChange={(event) => updateDraft(mark.student_id, { marks_obtained: event.target.value })} className="w-28" /></td>
                      <td className="px-4 py-3"><input type="checkbox" checked={draft.is_absent} onChange={(event) => updateDraft(mark.student_id, { is_absent: event.target.checked, marks_obtained: event.target.checked ? "" : draft.marks_obtained })} /></td>
                      <td className="px-4 py-3 text-slate-600">{mark.grade || "-"}</td>
                      <td className="px-4 py-3"><span className={`rounded-full px-2 py-1 text-xs font-semibold ${statusClass(mark.pass_status)}`}>{mark.pass_status}</span></td>
                      <td className="px-4 py-3"><Input value={draft.remarks} onChange={(event) => updateDraft(mark.student_id, { remarks: event.target.value })} placeholder="Optional" /></td>
                    </tr>
                  );
                })}
                {marks.length === 0 && <tr><td colSpan={6} className="px-4 py-6 text-center text-slate-500">Select an exam subject to enter marks.</td></tr>}
              </tbody>
            </table>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button type="button" onClick={saveMarks} disabled={saving || !marks.length} className="flex items-center gap-2"><Save size={16} /> Save Marks</Button>
            <button type="button" onClick={loadMarks} className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700">Reload Marks</button>
          </div>
        </AppSection>
      )}

      {!loading && tab === "reports" && (
        <div className="space-y-6">
          <AppSection title="Result reports" description="View class-wise and subject-wise result before or after publishing.">
            <div className="grid gap-3 md:grid-cols-[1fr_1fr_auto]">
              <div>
                <Label>Exam</Label>
                <SelectBox value={selectedExamId} onChange={(value) => { setSelectedExamId(value); setSelectedSubjectId(""); }}>
                  <option value="">Select exam</option>
                  {exams.map((exam) => <option key={exam.id} value={exam.id}>{exam.name} · {exam.class_name}</option>)}
                </SelectBox>
              </div>
              <div>
                <Label>Subject</Label>
                <SelectBox value={selectedSubjectId} onChange={setSelectedSubjectId}>
                  <option value="">Class-wise only</option>
                  {examSubjects.map((subject) => <option key={subject.id} value={subject.id}>{subject.subject_name}</option>)}
                </SelectBox>
              </div>
              <div className="flex items-end"><Button onClick={loadReports} type="button" className="flex items-center gap-2"><Eye size={16} /> View</Button></div>
            </div>
          </AppSection>

          {classResult && (
            <AppSection title="Class-wise result" description={`${classResult.exam.name} · ${classResult.exam.class_name}${classResult.exam.section_name ? ` - ${classResult.exam.section_name}` : ""}`}>
              <div className="mb-4 grid gap-3 md:grid-cols-4">
                <Card><p className="text-xs text-slate-500">Students</p><p className="text-2xl font-bold">{classResult.summary.total_students}</p></Card>
                <Card><p className="text-xs text-slate-500">Passed</p><p className="text-2xl font-bold text-emerald-700">{classResult.summary.passed}</p></Card>
                <Card><p className="text-xs text-slate-500">Failed</p><p className="text-2xl font-bold text-red-700">{classResult.summary.failed}</p></Card>
                <Card><p className="text-xs text-slate-500">Average %</p><p className="text-2xl font-bold">{classResult.summary.average_percentage}</p></Card>
              </div>
              <div className="overflow-x-auto rounded-2xl border border-slate-200">
                <table className="min-w-full divide-y divide-slate-200 text-sm">
                  <thead className="bg-slate-50 text-left text-slate-600"><tr><th className="px-4 py-3">Student</th><th className="px-4 py-3">Marks</th><th className="px-4 py-3">%</th><th className="px-4 py-3">Grade</th><th className="px-4 py-3">Status</th></tr></thead>
                  <tbody className="divide-y divide-slate-100">
                    {classResult.results.map((item) => (
                      <tr key={item.student_id}><td className="px-4 py-3"><p className="font-semibold">{item.student_name}</p><p className="text-xs text-slate-500">{item.admission_no}</p></td><td className="px-4 py-3">{item.marks_obtained}/{item.total_marks}</td><td className="px-4 py-3">{item.percentage}%</td><td className="px-4 py-3">{item.grade}</td><td className="px-4 py-3"><span className={`rounded-full px-2 py-1 text-xs font-semibold ${statusClass(item.pass_status)}`}>{item.pass_status}</span></td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </AppSection>
          )}

          {subjectResult && (
            <AppSection title="Subject-wise result" description={subjectResult.exam_subject.subject_name || "Subject result"}>
              <div className="mb-4 grid gap-3 md:grid-cols-4">
                <Card><p className="text-xs text-slate-500">Students</p><p className="text-2xl font-bold">{subjectResult.summary.total_students}</p></Card>
                <Card><p className="text-xs text-slate-500">Passed</p><p className="text-2xl font-bold text-emerald-700">{subjectResult.summary.passed}</p></Card>
                <Card><p className="text-xs text-slate-500">Failed/Absent</p><p className="text-2xl font-bold text-red-700">{subjectResult.summary.failed}</p></Card>
                <Card><p className="text-xs text-slate-500">Average Marks</p><p className="text-2xl font-bold">{subjectResult.summary.average_marks}</p></Card>
              </div>
              <div className="overflow-x-auto rounded-2xl border border-slate-200">
                <table className="min-w-full divide-y divide-slate-200 text-sm">
                  <thead className="bg-slate-50 text-left text-slate-600"><tr><th className="px-4 py-3">Student</th><th className="px-4 py-3">Marks</th><th className="px-4 py-3">Grade</th><th className="px-4 py-3">Status</th></tr></thead>
                  <tbody className="divide-y divide-slate-100">
                    {subjectResult.results.map((item) => (
                      <tr key={item.student_id}><td className="px-4 py-3"><p className="font-semibold">{item.student_name}</p><p className="text-xs text-slate-500">{item.admission_no}</p></td><td className="px-4 py-3">{item.is_absent ? "Absent" : item.marks_obtained ?? "-"}/{item.max_marks}</td><td className="px-4 py-3">{item.grade || "-"}</td><td className="px-4 py-3"><span className={`rounded-full px-2 py-1 text-xs font-semibold ${statusClass(item.pass_status)}`}>{item.pass_status}</span></td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </AppSection>
          )}
        </div>
      )}
    </div>
  );
}

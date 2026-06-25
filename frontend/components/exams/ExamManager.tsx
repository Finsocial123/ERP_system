"use client";

import { useEffect, useMemo, useState } from "react";
import { CalendarDays, CheckCircle2, Clock, Edit2, Eye, Loader2, MapPin, Plus, RefreshCcw, Save, Search, Trash2 } from "lucide-react";

import { AppSection } from "@/components/CrudManager";
import { Button, Card, Input, Label, Textarea } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import type { ClassResult, Exam, ExamMark, ExamMeta, ExamSubject, ExamTimetableItem, SubjectResult } from "@/types";

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
  start_time: string;
  end_time: string;
  room: string;
  timetable_note: string;
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
  start_time: "09:00",
  end_time: "12:00",
  room: "",
  timetable_note: "",
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
  if (status === "PASS" || status === "PUBLISHED" || status === "MANUAL") return "bg-emerald-50 text-emerald-700";
  if (status === "FAIL" || status === "ABSENT") return "bg-red-50 text-red-700";
  if (status === "AUTO_FROM_EXAM_START") return "bg-sky-50 text-sky-700";
  return "bg-amber-50 text-amber-700";
}

function displayDate(value?: string | null) {
  if (!value) return "-";
  return value.slice(0, 10);
}

function displayTime(value?: string | null) {
  if (!value) return "-";
  return value.slice(0, 5);
}

function numberOrNull(value: string) {
  if (value.trim() === "") return null;
  return Number(value);
}

function LoadingTableRow({ colSpan, text }: { colSpan: number; text: string }) {
  return (
    <tr>
      <td colSpan={colSpan} className="px-4 py-3">
        <span className="mx-auto flex w-fit items-center gap-2 rounded-full bg-slate-50 px-3 py-1.5 text-sm font-medium text-slate-600">
          <Loader2 size={16} className="animate-spin" />
          {text}
        </span>
      </td>
    </tr>
  );
}

function InlineLoader({ text }: { text: string }) {
  return (
    <span className="inline-flex items-center gap-2 rounded-full bg-slate-50 px-3 py-1.5 text-sm font-medium text-slate-600">
      <Loader2 size={16} className="animate-spin" />
      {text}
    </span>
  );
}

export default function ExamManager({ mode = "admin" }: { mode?: "admin" | "teacher" }) {
  const [tab, setTab] = useState<"exams" | "subjects" | "timetable" | "marks" | "reports">("exams");
  const [meta, setMeta] = useState<ExamMeta | null>(null);
  const [exams, setExams] = useState<Exam[]>([]);
  const [selectedExamId, setSelectedExamId] = useState("");
  const [examSubjects, setExamSubjects] = useState<ExamSubject[]>([]);
  const [examTimetable, setExamTimetable] = useState<ExamTimetableItem[]>([]);
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
  const [autoStartTime, setAutoStartTime] = useState("09:00");
  const [autoEndTime, setAutoEndTime] = useState("12:00");
  const [autoRoom, setAutoRoom] = useState("");
  const [autoOverride, setAutoOverride] = useState(false);
  const [loading, setLoading] = useState(true);
  const [examListLoading, setExamListLoading] = useState(false);
  const [subjectListLoading, setSubjectListLoading] = useState(false);
  const [timetableLoading, setTimetableLoading] = useState(false);
  const [marksLoading, setMarksLoading] = useState(false);
  const [reportsLoading, setReportsLoading] = useState(false);
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
    if (!examClass) return [];
    return meta.subjects.filter((item) => item.extra === examClass);
  }, [examForm.class_id, meta, selectedExam?.class_id]);

  const sectionIdForName = (classId?: number | null, sectionName?: string | null) => {
    if (!meta || !classId || !sectionName) return null;
    const match = meta.sections.find((item) => item.extra === String(classId) && item.name.trim().toLowerCase() === sectionName.trim().toLowerCase());
    return match?.id ?? null;
  };

  const loadData = async (showPageLoader = false) => {
    const shouldShowPageLoader = showPageLoader || !meta;
    if (shouldShowPageLoader) {
      setLoading(true);
    } else {
      setExamListLoading(true);
    }
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
      if (shouldShowPageLoader) {
        setLoading(false);
      } else {
        setExamListLoading(false);
      }
    }
  };

  const loadSubjects = async (examId: string) => {
    if (!examId) {
      setExamSubjects([]);
      setExamTimetable([]);
      setSelectedSubjectId("");
      return;
    }
    setSubjectListLoading(true);
    try {
      const data = await apiFetch<ExamSubject[]>(`/exams/${examId}/subjects`);
      setExamSubjects(data);
      setSelectedSubjectId((prev) => (prev && data.some((item) => String(item.id) === prev) ? prev : data.length ? String(data[0].id) : ""));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load exam subjects");
    } finally {
      setSubjectListLoading(false);
    }
  };

  const loadTimetable = async () => {
    if (!selectedExamId) {
      setExamTimetable([]);
      return;
    }
    setTimetableLoading(true);
    try {
      const data = await apiFetch<ExamTimetableItem[]>(`/exams/${selectedExamId}/timetable`);
      setExamTimetable(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load exam timetable");
    } finally {
      setTimetableLoading(false);
    }
  };

  const loadMarks = async () => {
    if (!selectedExamId || !selectedSubjectId) {
      setMarks([]);
      setMarkDrafts({});
      return;
    }
    setMarksLoading(true);
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
    } finally {
      setMarksLoading(false);
    }
  };

  const loadReports = async () => {
    if (!selectedExamId) {
      setClassResult(null);
      setSubjectResult(null);
      return;
    }
    setReportsLoading(true);
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
    } finally {
      setReportsLoading(false);
    }
  };

  useEffect(() => {
    loadData(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    loadSubjects(selectedExamId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedExamId]);

  useEffect(() => {
    if (tab === "timetable") loadTimetable();
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
      section_id: exam.section_name ? String(sectionIdForName(exam.class_id, exam.section_name) ?? "") : exam.section_id ? String(exam.section_id) : "",
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
      start_time: subjectForm.start_time || null,
      end_time: subjectForm.end_time || null,
      room: subjectForm.room.trim() || null,
      timetable_note: subjectForm.timetable_note.trim() || null,
    };
    try {
      const saved = await apiFetch<ExamSubject>(editingSubject ? `/exams/${selectedExamId}/subjects/${editingSubject.id}` : `/exams/${selectedExamId}/subjects`, {
        method: editingSubject ? "PUT" : "POST",
        body: JSON.stringify(payload),
      });
      setSelectedSubjectId(String(saved.id));
      setSuccess(editingSubject ? "Exam subject and timetable updated successfully" : "Exam subject added to timetable successfully");
      resetSubject();
      await loadSubjects(selectedExamId);
      await loadTimetable();
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
      start_time: subject.start_time ? subject.start_time.slice(0, 5) : "09:00",
      end_time: subject.end_time ? subject.end_time.slice(0, 5) : "12:00",
      room: subject.room || "",
      timetable_note: subject.timetable_note || "",
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
      await loadTimetable();
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to remove subject");
    }
  };

  const autoScheduleTimetable = async () => {
    if (!selectedExamId) {
      setError("Select an exam first");
      return;
    }
    setSaving(true);
    setError("");
    setSuccess("");
    const params = new URLSearchParams({
      start_time: autoStartTime,
      end_time: autoEndTime,
      override_existing: String(autoOverride),
    });
    if (autoRoom.trim()) params.set("room", autoRoom.trim());
    try {
      await apiFetch<ExamSubject[]>(`/exams/${selectedExamId}/auto-schedule-timetable?${params.toString()}`, { method: "POST" });
      setSuccess("Exam timetable generated from exam dates successfully");
      await loadSubjects(selectedExamId);
      await loadTimetable();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to auto schedule timetable");
    } finally {
      setSaving(false);
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

  const refreshCurrentTab = async () => {
    if (tab === "exams") {
      await loadData();
      return;
    }

    const tasks: Promise<void>[] = [loadData()];
    if (tab === "subjects") tasks.push(loadSubjects(selectedExamId));
    if (tab === "timetable") tasks.push(loadTimetable());
    if (tab === "marks") tasks.push(loadMarks());
    if (tab === "reports") tasks.push(loadReports());
    await Promise.all(tasks);
  };

  const moduleReady = Boolean(meta);
  const isRefreshing = examListLoading || subjectListLoading || timetableLoading || marksLoading || reportsLoading;
  const selectedExamLabel = selectedExam ? `${selectedExam.name} · ${selectedExam.class_name || "Class"}${selectedExam.section_name ? ` - ${selectedExam.section_name}` : ""}` : "Select an exam";

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-3 md:flex-row md:items-center">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Exam and Result Management</h1>
          <p className="text-sm text-slate-500">Create exams, prepare exam timetable, enter marks, publish results and view reports.</p>
        </div>
        <Button onClick={refreshCurrentTab} disabled={loading || isRefreshing} className="flex items-center gap-2">
          <RefreshCcw size={16} className={isRefreshing ? "animate-spin" : ""} /> {isRefreshing ? "Refreshing..." : "Refresh"}
        </Button>
      </div>

      {error && <div className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</div>}
      {success && <div className="rounded-xl bg-emerald-50 p-3 text-sm text-emerald-700">{success}</div>}

      <div className="flex flex-wrap gap-2">
        {[
          ["exams", "Create Exam"],
          ["subjects", "Exam Subjects"],
          ["timetable", "Exam Timetable"],
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

      {loading && !moduleReady && <Card><InlineLoader text="Loading exam module..." /></Card>}

      {moduleReady && tab === "exams" && (
        <div className="grid gap-6 xl:grid-cols-[420px_1fr]">
          <AppSection title={editingExam ? "Edit exam" : "Create exam"} description="Choose class, optional section, exam date range and academic session.">
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

          <AppSection title="Exam list" description="Select an exam to manage timetable, subjects, marks and reports.">
            <form onSubmit={applySearch} className="mb-4 grid gap-3 md:grid-cols-[1fr_180px_auto]">
              <div className="relative">
                <Search className="absolute left-3 top-2.5 text-slate-400" size={16} />
                <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search exams" className="pl-9" />
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
                  {examListLoading && <LoadingTableRow colSpan={5} text="Refreshing exam list..." />}
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
                          <button type="button" onClick={() => { setSelectedExamId(String(exam.id)); setTab("timetable"); }} className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700">Timetable</button>
                          <button type="button" onClick={() => publishToggle(exam)} className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700">{exam.result_status === "PUBLISHED" ? "Unpublish" : "Publish"}</button>
                          <button type="button" onClick={() => deleteExam(exam)} className="rounded-lg border border-red-100 p-2 text-red-600"><Trash2 size={14} /></button>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {!examListLoading && exams.length === 0 && <tr><td colSpan={5} className="px-4 py-6 text-center text-slate-500">No exams found.</td></tr>}
                </tbody>
              </table>
            </div>
          </AppSection>
        </div>
      )}

      {moduleReady && tab === "subjects" && (
        <div className="grid gap-6 xl:grid-cols-[420px_1fr]">
          <AppSection title={editingSubject ? "Edit exam subject" : "Add exam subject"} description="Adding a subject also creates its timetable row. You can set date/time now or auto-generate later.">
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
                  <option value="">{selectedExam || examForm.class_id ? "Select subject" : "Select exam/class first"}</option>
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
              <div className="grid gap-4 md:grid-cols-3">
                <div>
                  <Label>Exam Date</Label>
                  <Input type="date" value={subjectForm.exam_date} onChange={(event) => setSubjectForm({ ...subjectForm, exam_date: event.target.value })} />
                </div>
                <div>
                  <Label>Start Time</Label>
                  <Input type="time" value={subjectForm.start_time} onChange={(event) => setSubjectForm({ ...subjectForm, start_time: event.target.value })} />
                </div>
                <div>
                  <Label>End Time</Label>
                  <Input type="time" value={subjectForm.end_time} onChange={(event) => setSubjectForm({ ...subjectForm, end_time: event.target.value })} />
                </div>
              </div>
              <div>
                <Label>Room / Hall</Label>
                <Input value={subjectForm.room} onChange={(event) => setSubjectForm({ ...subjectForm, room: event.target.value })} placeholder="Room 101 / Main Hall" />
              </div>
              <div>
                <Label>Timetable Instructions</Label>
                <Textarea value={subjectForm.timetable_note} onChange={(event) => setSubjectForm({ ...subjectForm, timetable_note: event.target.value })} placeholder="Bring admit card, calculator allowed, etc." />
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
                    <th className="px-4 py-3">Schedule</th>
                    <th className="px-4 py-3">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {subjectListLoading && <LoadingTableRow colSpan={5} text="Refreshing exam subjects..." />}
                  {examSubjects.map((subject) => (
                    <tr key={subject.id} className={selectedSubjectId === String(subject.id) ? "bg-slate-50" : "bg-white"}>
                      <td className="px-4 py-3"><button type="button" onClick={() => setSelectedSubjectId(String(subject.id))} className="font-semibold text-slate-900 hover:underline">{subject.subject_name}</button><p className="text-xs text-slate-500">{subject.marks_entered_count} marks entered</p></td>
                      <td className="px-4 py-3 text-slate-600">{subject.teacher_name || "-"}</td>
                      <td className="px-4 py-3 text-slate-600">Max {subject.max_marks} · Pass {subject.pass_marks}</td>
                      <td className="px-4 py-3 text-slate-600">{displayDate(subject.exam_date)} · {displayTime(subject.start_time)} - {displayTime(subject.end_time)}<p className="text-xs text-slate-400">{subject.room || "No room set"}</p></td>
                      <td className="px-4 py-3">
                        <div className="flex gap-2">
                          <button type="button" onClick={() => editSubject(subject)} className="rounded-lg border border-slate-200 p-2 text-slate-600"><Edit2 size={14} /></button>
                          <button type="button" onClick={() => deleteSubject(subject)} className="rounded-lg border border-red-100 p-2 text-red-600"><Trash2 size={14} /></button>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {!subjectListLoading && examSubjects.length === 0 && <tr><td colSpan={5} className="px-4 py-6 text-center text-slate-500">No subjects added for this exam.</td></tr>}
                </tbody>
              </table>
            </div>
          </AppSection>
        </div>
      )}

      {moduleReady && tab === "timetable" && (
        <div className="space-y-6">
          <AppSection title="Build exam timetable" description="Students can see this timetable from their Exam page even before results are published.">
            <div className="grid gap-3 md:grid-cols-[1fr_auto]">
              <div>
                <Label>Selected Exam</Label>
                <SelectBox value={selectedExamId} onChange={setSelectedExamId} required>
                  <option value="">Select exam</option>
                  {exams.map((exam) => <option key={exam.id} value={exam.id}>{exam.name} · {exam.class_name}</option>)}
                </SelectBox>
              </div>
              <div className="flex items-end gap-2">
                <Button type="button" onClick={loadTimetable} disabled={!selectedExamId || timetableLoading} className="flex items-center gap-2">{timetableLoading ? <Loader2 size={16} className="animate-spin" /> : <Eye size={16} />} {timetableLoading ? "Loading..." : "View"}</Button>
                <button type="button" onClick={() => setTab("subjects")} className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700">Add / Edit Subjects</button>
              </div>
            </div>
          </AppSection>

          <AppSection title="Automatic timetable generator" description="Uses the exam start date and assigns one subject per day in subject order. Manual subject dates are kept unless override is enabled.">
            <div className="grid gap-4 md:grid-cols-5">
              <div>
                <Label>Start Time</Label>
                <Input type="time" value={autoStartTime} onChange={(event) => setAutoStartTime(event.target.value)} />
              </div>
              <div>
                <Label>End Time</Label>
                <Input type="time" value={autoEndTime} onChange={(event) => setAutoEndTime(event.target.value)} />
              </div>
              <div>
                <Label>Room</Label>
                <Input value={autoRoom} onChange={(event) => setAutoRoom(event.target.value)} placeholder="Optional" />
              </div>
              <label className="flex items-end gap-2 pb-2 text-sm font-semibold text-slate-700">
                <input type="checkbox" checked={autoOverride} onChange={(event) => setAutoOverride(event.target.checked)} /> Override existing
              </label>
              <div className="flex items-end">
                <Button type="button" onClick={autoScheduleTimetable} disabled={saving || !selectedExamId} className="flex items-center gap-2"><CalendarDays size={16} /> Auto Schedule</Button>
              </div>
            </div>
          </AppSection>

          <AppSection title="Exam timetable preview" description={selectedExamLabel}>
            <div className="mb-4 grid gap-3 md:grid-cols-3">
              <Card className="flex items-center gap-3"><CalendarDays className="text-slate-400" size={20} /><div><p className="text-xs text-slate-500">Exam Dates</p><p className="font-semibold text-slate-900">{displayDate(selectedExam?.start_date)} - {displayDate(selectedExam?.end_date)}</p></div></Card>
              <Card className="flex items-center gap-3"><CheckCircle2 className="text-slate-400" size={20} /><div><p className="text-xs text-slate-500">Subjects</p><p className="font-semibold text-slate-900">{examSubjects.length}</p></div></Card>
              <Card className="flex items-center gap-3"><Clock className="text-slate-400" size={20} /><div><p className="text-xs text-slate-500">Default Auto Time</p><p className="font-semibold text-slate-900">{autoStartTime} - {autoEndTime}</p></div></Card>
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
                    <th className="px-4 py-3">Source</th>
                    <th className="px-4 py-3">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {timetableLoading && <LoadingTableRow colSpan={7} text="Refreshing timetable..." />}
                  {examTimetable.map((item) => (
                    <tr key={item.exam_subject_id}>
                      <td className="px-4 py-3 font-semibold text-slate-900">{displayDate(item.exam_date)}</td>
                      <td className="px-4 py-3 text-slate-600">{displayTime(item.start_time)} - {displayTime(item.end_time)}</td>
                      <td className="px-4 py-3"><p className="font-semibold text-slate-900">{item.subject_name}</p><p className="text-xs text-slate-500">Max {item.max_marks} · Pass {item.pass_marks}</p>{item.timetable_note && <p className="mt-1 text-xs text-slate-500">{item.timetable_note}</p>}</td>
                      <td className="px-4 py-3 text-slate-600">{item.teacher_name || "-"}</td>
                      <td className="px-4 py-3 text-slate-600">{item.room || "-"}</td>
                      <td className="px-4 py-3"><span className={`rounded-full px-2 py-1 text-xs font-semibold ${statusClass(item.schedule_source)}`}>{item.schedule_source === "AUTO_FROM_EXAM_START" ? "AUTO" : item.schedule_source}</span></td>
                      <td className="px-4 py-3"><button type="button" onClick={() => { const subject = examSubjects.find((row) => row.id === item.exam_subject_id); if (subject) editSubject(subject); else setTab("subjects"); }} className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700">Edit</button></td>
                    </tr>
                  ))}
                  {!timetableLoading && examTimetable.length === 0 && <tr><td colSpan={7} className="px-4 py-6 text-center text-slate-500">No timetable rows yet. Add subjects or use auto schedule.</td></tr>}
                </tbody>
              </table>
            </div>
          </AppSection>
        </div>
      )}

      {moduleReady && tab === "marks" && (
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

          {selectedSubject && <p className="mb-4 rounded-xl bg-slate-50 p-3 text-sm text-slate-600">Selected subject: <b>{selectedSubject.subject_name}</b> · Exam: {displayDate(selectedSubject.exam_date)} · {displayTime(selectedSubject.start_time)} - {displayTime(selectedSubject.end_time)} · Max marks: {selectedSubject.max_marks} · Pass marks: {selectedSubject.pass_marks}</p>}

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
                {marksLoading && <LoadingTableRow colSpan={6} text="Refreshing marks..." />}
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
                {!marksLoading && marks.length === 0 && <tr><td colSpan={6} className="px-4 py-6 text-center text-slate-500">Select an exam subject to enter marks.</td></tr>}
              </tbody>
            </table>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button type="button" onClick={saveMarks} disabled={saving || !marks.length} className="flex items-center gap-2"><Save size={16} /> Save Marks</Button>
            <button type="button" onClick={loadMarks} disabled={marksLoading} className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 disabled:cursor-not-allowed disabled:opacity-60">{marksLoading && <Loader2 size={16} className="animate-spin" />} {marksLoading ? "Reloading..." : "Reload Marks"}</button>
          </div>
        </AppSection>
      )}

      {moduleReady && tab === "reports" && (
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
              <div className="flex items-end"><Button onClick={loadReports} type="button" disabled={reportsLoading} className="flex items-center gap-2">{reportsLoading ? <Loader2 size={16} className="animate-spin" /> : <Eye size={16} />} {reportsLoading ? "Loading..." : "View"}</Button></div>
            </div>
          </AppSection>

          {reportsLoading && <Card><InlineLoader text="Refreshing result reports..." /></Card>}

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

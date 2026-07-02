"use client";

import { useEffect, useMemo, useState } from "react";
import type React from "react";
import {
  BarChart3,
  BookOpen,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock3,
  Edit2,
  FileText,
  PlayCircle,
  Plus,
  RefreshCcw,
  Trash2,
  UploadCloud,
  Users,
  X,
} from "lucide-react";

import { AppSection } from "@/components/CrudManager";
import { Button, Card, Input, Label, Textarea } from "@/components/ui";
import { apiFetch, apiUpload, fileUrl } from "@/lib/api";
import type { CourseMeta, LMSCourse, LMSCourseProgressReport, LMSLesson, LMSStudentProgress } from "@/types";

type Props = {
  mode: "admin" | "teacher";
};

type CourseForm = {
  title: string;
  description: string;
  class_id: string;
  section_id: string;
  subject_id: string;
  teacher_id: string;
  status: string;
  thumbnail: File | null;
};

type LessonForm = {
  title: string;
  description: string;
  order: string;
  language: string;
  external_video_link: string;
  video: File | null;
  pdf: File | null;
};

const emptyCourse: CourseForm = {
  title: "",
  description: "",
  class_id: "",
  section_id: "",
  subject_id: "",
  teacher_id: "",
  status: "PUBLISHED",
  thumbnail: null,
};

const emptyLesson: LessonForm = {
  title: "",
  description: "",
  order: "1",
  language: "en",
  external_video_link: "",
  video: null,
  pdf: null,
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

function statusClass(value: string) {
  if (value === "PUBLISHED") return "bg-green-50 text-green-700";
  if (value === "DRAFT") return "bg-amber-50 text-amber-700";
  return "bg-slate-100 text-slate-700";
}

function progressStatusClass(value: string) {
  if (value === "COMPLETED") return "bg-green-50 text-green-700";
  if (value === "IN_PROGRESS") return "bg-blue-50 text-blue-700";
  if (value === "NO_LESSONS") return "bg-slate-100 text-slate-600";
  return "bg-amber-50 text-amber-700";
}

function progressStatusLabel(value: string) {
  if (value === "COMPLETED") return "Completed";
  if (value === "IN_PROGRESS") return "In progress";
  if (value === "NO_LESSONS") return "No lessons";
  return "Not started";
}

function formatDate(value?: string | null) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

function formatFileSize(file?: File | null) {
  if (!file) return "";
  const mb = file.size / (1024 * 1024);
  if (mb >= 1024) return `${(mb / 1024).toFixed(2)} GB`;
  return `${mb.toFixed(1)} MB`;
}

function ProgressBar({ value }: { value: number }) {
  const safeValue = Math.max(0, Math.min(100, Number(value || 0)));
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
      <div className="h-full rounded-full bg-slate-900 transition-all" style={{ width: `${safeValue}%` }} />
    </div>
  );
}

export default function CourseManager({ mode }: Props) {
  const [meta, setMeta] = useState<CourseMeta | null>(null);
  const [courses, setCourses] = useState<LMSCourse[]>([]);
  const [courseForm, setCourseForm] = useState<CourseForm>(emptyCourse);
  const [lessonForm, setLessonForm] = useState<LessonForm>(emptyLesson);
  const [editing, setEditing] = useState<LMSCourse | null>(null);
  const [editingLesson, setEditingLesson] = useState<LMSLesson | null>(null);
  const [selected, setSelected] = useState<LMSCourse | null>(null);
  const [lessons, setLessons] = useState<LMSLesson[]>([]);
  const [progressReport, setProgressReport] = useState<LMSCourseProgressReport | null>(null);
  const [expandedStudentId, setExpandedStudentId] = useState<number | null>(null);
  const [search, setSearch] = useState("");
  const [classFilter, setClassFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadingReport, setLoadingReport] = useState(false);
  const [savingCourse, setSavingCourse] = useState(false);
  const [savingLesson, setSavingLesson] = useState(false);
  const [lessonUploadProgress, setLessonUploadProgress] = useState<number | null>(null);
  const [lessonUploadStatus, setLessonUploadStatus] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const filteredSections = useMemo(() => {
    if (!meta) return [];
    const classId = courseForm.class_id;
    if (!classId) return meta.sections;
    return meta.sections.filter((section) => section.extra === classId);
  }, [courseForm.class_id, meta]);

  const filteredSubjects = useMemo(() => {
    if (!meta || !courseForm.class_id) return [];
    return meta.subjects.filter((subject) => subject.extra === courseForm.class_id);
  }, [courseForm.class_id, meta]);

  const sectionIdForName = (classId?: number | null, sectionName?: string | null) => {
    if (!meta || !classId || !sectionName) return null;
    const match = meta.sections.find((item) => item.extra === String(classId) && item.name.trim().toLowerCase() === sectionName.trim().toLowerCase());
    return match?.id ?? null;
  };

  const visibleCourses = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return courses;
    return courses.filter((course) =>
      [course.title, course.class_name, course.section_name, course.subject_name, course.teacher_name]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(q)),
    );
  }, [courses, search]);

  const reportStudents = progressReport?.students || [];

  const loadData = async () => {
    setLoading(true);
    setError("");
    try {
      const coursePath = classFilter ? `/courses/?class_id=${classFilter}` : "/courses/";
      const [metaData, courseData] = await Promise.all([
        apiFetch<CourseMeta>("/courses/meta"),
        apiFetch<LMSCourse[]>(coursePath),
      ]);
      setMeta(metaData);
      setCourses(courseData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load LMS courses");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [classFilter]);

  const loadLessons = async (course: LMSCourse) => {
    setSelected(course);
    setError("");
    setLoadingReport(true);
    try {
      const [lessonRows, report] = await Promise.all([
        apiFetch<LMSLesson[]>(`/lessons/course/${course.id}`),
        apiFetch<LMSCourseProgressReport>(`/courses/${course.id}/students/progress`),
      ]);
      setLessons(lessonRows);
      setLessonForm({ ...emptyLesson, order: String(lessonRows.length + 1) });
      setEditingLesson(null);
      setProgressReport(report);
      setExpandedStudentId(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load course lessons/report");
    } finally {
      setLoadingReport(false);
    }
  };

  const refreshProgressReport = async () => {
    if (!selected) return;
    setLoadingReport(true);
    setError("");
    try {
      const report = await apiFetch<LMSCourseProgressReport>(`/courses/${selected.id}/students/progress`);
      setProgressReport(report);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to refresh progress report");
    } finally {
      setLoadingReport(false);
    }
  };

  const updateCourse = (key: keyof CourseForm, value: string | File | null) => {
    setCourseForm((prev) => ({ ...prev, [key]: value } as CourseForm));
    if (key === "class_id") setCourseForm((prev) => ({ ...prev, section_id: "", subject_id: "" }));
  };

  const updateLesson = (key: keyof LessonForm, value: string | File | null) => {
    setLessonForm((prev) => ({ ...prev, [key]: value } as LessonForm));
  };

  const resetCourseForm = () => {
    setCourseForm(emptyCourse);
    setEditing(null);
  };

  const resetLessonForm = () => {
    setLessonForm({ ...emptyLesson, order: String(lessons.length + 1) });
    setEditingLesson(null);
    setLessonUploadProgress(null);
    setLessonUploadStatus("");
  };

  const startEdit = (course: LMSCourse) => {
    setEditing(course);
    setCourseForm({
      title: course.title,
      description: course.description || "",
      class_id: course.class_id ? String(course.class_id) : "",
      section_id: course.section_name ? String(sectionIdForName(course.class_id, course.section_name) ?? "") : course.section_id ? String(course.section_id) : "",
      subject_id: course.subject_id ? String(course.subject_id) : "",
      teacher_id: course.teacher_id ? String(course.teacher_id) : "",
      status: course.status || "PUBLISHED",
      thumbnail: null,
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const startEditLesson = (lesson: LMSLesson) => {
    setEditingLesson(lesson);
    setLessonForm({
      title: lesson.title,
      description: lesson.description || "",
      order: String(lesson.order || 1),
      language: lesson.language || "en",
      external_video_link: lesson.external_video_link || "",
      video: null,
      pdf: null,
    });
    document.getElementById("lesson-form")?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const buildCourseData = () => {
    const data = new FormData();
    data.append("title", courseForm.title.trim());
    data.append("description", courseForm.description.trim());
    data.append("class_id", courseForm.class_id);
    if (courseForm.section_id) data.append("section_id", courseForm.section_id);
    if (courseForm.subject_id) data.append("subject_id", courseForm.subject_id);
    if (mode === "admin" && courseForm.teacher_id) data.append("teacher_id", courseForm.teacher_id);
    data.append("status", courseForm.status);
    if (courseForm.thumbnail) data.append("thumbnail", courseForm.thumbnail);
    return data;
  };

  const saveCourse = async (event: React.FormEvent) => {
    event.preventDefault();
    setSavingCourse(true);
    setError("");
    setSuccess("");
    try {
      const path = editing ? `/courses/${editing.id}` : "/courses/";
      const saved = await apiUpload<LMSCourse>(path, buildCourseData(), { method: editing ? "PUT" : "POST" });
      setSuccess(editing ? "Course updated successfully" : "Course created successfully");
      resetCourseForm();
      await loadData();
      await loadLessons(saved);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save course");
    } finally {
      setSavingCourse(false);
    }
  };

  const saveLesson = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!selected) return;
    setSavingLesson(true);
    setLessonUploadProgress(lessonForm.video || lessonForm.pdf ? 0 : null);
    setLessonUploadStatus(lessonForm.video || lessonForm.pdf ? "Preparing upload..." : "Saving lesson...");
    setError("");
    setSuccess("");
    try {
      const data = new FormData();
      data.append("title", lessonForm.title.trim());
      data.append("description", lessonForm.description.trim());
      data.append("order", lessonForm.order || "0");
      data.append("language", lessonForm.language || "en");
      if (lessonForm.external_video_link) data.append("external_video_link", lessonForm.external_video_link.trim());
      if (lessonForm.video) data.append("video", lessonForm.video);
      if (lessonForm.pdf) data.append("pdf", lessonForm.pdf);
      const response = await apiUpload<{ message?: string; video_ai_skipped_reason?: string | null }>(
        editingLesson ? `/lessons/${editingLesson.id}` : `/lessons/${selected.id}`,
        data,
        {
          method: editingLesson ? "PUT" : "POST",
          onUploadProgress: ({ percent }) => {
            setLessonUploadProgress(percent);
            setLessonUploadStatus(percent >= 100 ? "Upload complete. Saving lesson on server..." : `Uploading file... ${percent}%`);
          },
        },
      );
      setLessonForm({ ...emptyLesson, order: String(editingLesson ? lessons.length + 1 : lessons.length + 2) });
      setSuccess(response.video_ai_skipped_reason || (editingLesson ? "Lesson updated successfully" : "Lesson added successfully"));
      setEditingLesson(null);
      await loadLessons(selected);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : editingLesson ? "Failed to update lesson" : "Failed to save lesson");
    } finally {
      setSavingLesson(false);
      setLessonUploadStatus("");
      setLessonUploadProgress(null);
    }
  };

  const deleteCourse = async (course: LMSCourse) => {
    if (!confirm("Archive this course? Students will no longer see it.")) return;
    setError("");
    try {
      await apiFetch(`/courses/${course.id}`, { method: "DELETE" });
      if (selected?.id === course.id) {
        setSelected(null);
        setLessons([]);
        setProgressReport(null);
      }
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to archive course");
    }
  };

  const deleteLesson = async (lesson: LMSLesson) => {
    if (!confirm("Delete this lesson?")) return;
    setError("");
    try {
      await apiFetch(`/lessons/${lesson.id}`, { method: "DELETE" });
      if (selected) await loadLessons(selected);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete lesson");
    }
  };

  const syncEnrollments = async (course: LMSCourse) => {
    setError("");
    setSuccess("");
    try {
      const res = await apiFetch<{ message: string }>(`/courses/${course.id}/sync-enrollments`, { method: "POST" });
      setSuccess(res.message);
      await loadData();
      if (selected?.id === course.id) await loadLessons(course);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to sync enrollments");
    }
  };

  const toggleStudent = (student: LMSStudentProgress) => {
    setExpandedStudentId((current) => (current === student.student_user_id ? null : student.student_user_id));
  };

  return (
    <AppSection
      title={mode === "admin" ? "LMS Courses" : "My LMS Courses"}
      description="Create class-based courses, add video/PDF lessons, auto-enroll assigned students, and track lesson progress."
    >
      {error && <div className="mb-4 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
      {success && <div className="mb-4 rounded-xl bg-green-50 px-4 py-3 text-sm text-green-700">{success}</div>}

      <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
        <Card>
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-bold text-slate-900">{editing ? "Edit course" : "Create course"}</h2>
              <p className="text-sm text-slate-500">Map every course with class, section and subject.</p>
            </div>
            {editing && (
              <button type="button" onClick={resetCourseForm} className="rounded-xl border border-slate-200 p-2 text-slate-600 hover:bg-slate-100">
                <X size={18} />
              </button>
            )}
          </div>

          <form onSubmit={saveCourse} className="grid gap-4 md:grid-cols-2">
            <div className="md:col-span-2">
              <Label>Title</Label>
              <Input value={courseForm.title} required placeholder="Class 10 Physics" onChange={(e) => updateCourse("title", e.target.value)} />
            </div>
            <div className="md:col-span-2">
              <Label>Description</Label>
              <Textarea value={courseForm.description} placeholder="Course details" onChange={(e) => updateCourse("description", e.target.value)} />
            </div>
            <div>
              <Label>Class</Label>
              <SelectBox value={courseForm.class_id} onChange={(value) => updateCourse("class_id", value)} required>
                <option value="">Select class</option>
                {meta?.classes.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </SelectBox>
            </div>
            <div>
              <Label>Section</Label>
              <SelectBox value={courseForm.section_id} onChange={(value) => updateCourse("section_id", value)}>
                <option value="">All sections</option>
                {filteredSections.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </SelectBox>
            </div>
            <div>
              <Label>Subject</Label>
              <SelectBox value={courseForm.subject_id} onChange={(value) => updateCourse("subject_id", value)}>
                <option value="">{courseForm.class_id ? "Select subject" : "Select class first"}</option>
                {filteredSubjects.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </SelectBox>
            </div>
            {mode === "admin" && (
              <div>
                <Label>Teacher</Label>
                <SelectBox value={courseForm.teacher_id} onChange={(value) => updateCourse("teacher_id", value)}>
                  <option value="">Use my account</option>
                  {meta?.teachers.map((item, index) => <option key={`course-teacher-${item.id}-${index}`} value={item.id}>{item.name}</option>)}
                </SelectBox>
              </div>
            )}
            <div>
              <Label>Status</Label>
              <SelectBox value={courseForm.status} onChange={(value) => updateCourse("status", value)}>
                <option value="PUBLISHED">Published</option>
                <option value="DRAFT">Draft</option>
                <option value="ARCHIVED">Archived</option>
              </SelectBox>
            </div>
            <div>
              <Label>Thumbnail</Label>
              <label className="flex cursor-pointer items-center justify-between rounded-xl border border-dashed border-slate-300 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50">
                <span className="inline-flex items-center gap-2"><UploadCloud size={18} /> {courseForm.thumbnail ? courseForm.thumbnail.name : "Choose image"}</span>
                <input className="hidden" type="file" accept="image/*" onChange={(e) => updateCourse("thumbnail", e.target.files?.[0] || null)} />
              </label>
            </div>
            <div className="md:col-span-2">
              <Button type="submit" disabled={savingCourse || !courseForm.title || !courseForm.class_id}>
                <span className="inline-flex items-center gap-2"><Plus size={16} /> {savingCourse ? "Saving..." : editing ? "Update Course" : "Create Course"}</span>
              </Button>
            </div>
          </form>
        </Card>

        <Card>
          <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
            <div>
              <h2 className="text-lg font-bold text-slate-900">Course List</h2>
              <p className="text-sm text-slate-500">{loading ? "Loading..." : `${visibleCourses.length} course(s)`}</p>
            </div>
            <div className="grid gap-2 md:grid-cols-[1fr_160px_auto]">
              <Input placeholder="Search" value={search} onChange={(e) => setSearch(e.target.value)} />
              <SelectBox value={classFilter} onChange={setClassFilter}>
                <option value="">All classes</option>
                {meta?.classes.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </SelectBox>
              <button type="button" onClick={loadData} className="rounded-xl border border-slate-200 p-2 text-slate-700 hover:bg-slate-100"><RefreshCcw size={18} /></button>
            </div>
          </div>

          <div className="space-y-3">
            {visibleCourses.map((course) => (
              <div key={course.id} className={`rounded-2xl border p-4 ${selected?.id === course.id ? "border-slate-900 bg-slate-50" : "border-slate-200"}`}>
                <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                  <button type="button" onClick={() => loadLessons(course)} className="flex-1 text-left">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="font-bold text-slate-900">{course.title}</h3>
                      <span className={`rounded-full px-2 py-1 text-xs font-semibold ${statusClass(course.status)}`}>{course.status}</span>
                    </div>
                    <p className="mt-1 text-sm text-slate-500">
                      {course.class_name || "-"}{course.section_name ? ` · ${course.section_name}` : " · All sections"}{course.subject_name ? ` · ${course.subject_name}` : ""}
                    </p>
                    <p className="mt-1 text-sm text-slate-500">Teacher: {course.teacher_name || "-"} · Lessons: {course.lessons_count} · Students: {course.enrolled_students_count}</p>
                  </button>
                  <div className="flex flex-wrap gap-2">
                    <button type="button" title="Open lessons and progress" onClick={() => loadLessons(course)} className="rounded-xl border border-slate-200 p-2 text-slate-600 hover:bg-slate-100"><BookOpen size={16} /></button>
                    <button type="button" title="Sync students" onClick={() => syncEnrollments(course)} className="rounded-xl border border-slate-200 p-2 text-slate-600 hover:bg-slate-100"><Users size={16} /></button>
                    <button type="button" title="Edit course" onClick={() => startEdit(course)} className="rounded-xl border border-slate-200 p-2 text-slate-600 hover:bg-slate-100"><Edit2 size={16} /></button>
                    <button type="button" title="Archive course" onClick={() => deleteCourse(course)} className="rounded-xl border border-red-200 p-2 text-red-600 hover:bg-red-50"><Trash2 size={16} /></button>
                  </div>
                </div>
              </div>
            ))}
            {!loading && visibleCourses.length === 0 && <div className="rounded-2xl border border-dashed border-slate-200 p-6 text-center text-sm text-slate-500">No courses found.</div>}
          </div>
        </Card>
      </div>

      <Card className="mt-6">
        {!selected ? (
          <div className="rounded-2xl border border-dashed border-slate-200 p-6 text-center text-sm text-slate-500">Select a course to add lessons and view student progress.</div>
        ) : (
          <>
            <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
              <div>
                <h2 className="text-lg font-bold text-slate-900">Lessons and progress for {selected.title}</h2>
                <p className="text-sm text-slate-500">Manage course content and check which students completed the lessons.</p>
              </div>
              <button type="button" onClick={refreshProgressReport} className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100">
                <RefreshCcw size={16} /> {loadingReport ? "Loading..." : "Refresh report"}
              </button>
            </div>

            <div className="mb-6 rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <div className="mb-4 flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                <div>
                  <h3 className="inline-flex items-center gap-2 font-bold text-slate-900"><BarChart3 size={18} /> Student Progress Report</h3>
                  <p className="text-sm text-slate-500">Auto-calculated from completed lessons. Use sync if newly added students are missing.</p>
                </div>
                <button type="button" onClick={() => syncEnrollments(selected)} className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100">
                  <Users size={16} /> Sync students
                </button>
              </div>

              <div className="mb-4 grid gap-3 md:grid-cols-5">
                <div className="rounded-2xl bg-white p-3 shadow-sm">
                  <p className="text-xs font-semibold uppercase text-slate-400">Students</p>
                  <p className="text-2xl font-bold text-slate-900">{progressReport?.total_students ?? 0}</p>
                </div>
                <div className="rounded-2xl bg-white p-3 shadow-sm">
                  <p className="text-xs font-semibold uppercase text-slate-400">Average</p>
                  <p className="text-2xl font-bold text-slate-900">{progressReport?.average_progress ?? 0}%</p>
                </div>
                <div className="rounded-2xl bg-white p-3 shadow-sm">
                  <p className="text-xs font-semibold uppercase text-slate-400">Completed</p>
                  <p className="text-2xl font-bold text-green-700">{progressReport?.completed_students ?? 0}</p>
                </div>
                <div className="rounded-2xl bg-white p-3 shadow-sm">
                  <p className="text-xs font-semibold uppercase text-slate-400">In progress</p>
                  <p className="text-2xl font-bold text-blue-700">{progressReport?.in_progress_students ?? 0}</p>
                </div>
                <div className="rounded-2xl bg-white p-3 shadow-sm">
                  <p className="text-xs font-semibold uppercase text-slate-400">Not started</p>
                  <p className="text-2xl font-bold text-amber-700">{progressReport?.not_started_students ?? 0}</p>
                </div>
              </div>

              <div className="space-y-3">
                {loadingReport && <div className="rounded-2xl border border-dashed border-slate-200 bg-white p-4 text-sm text-slate-500">Loading progress report...</div>}
                {!loadingReport && reportStudents.map((student) => (
                  <div key={student.student_user_id} className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
                    <button type="button" onClick={() => toggleStudent(student)} className="w-full p-4 text-left hover:bg-slate-50">
                      <div className="grid gap-4 lg:grid-cols-[1.3fr_1fr_120px] lg:items-center">
                        <div className="flex gap-3">
                          <span className="mt-1 text-slate-500">{expandedStudentId === student.student_user_id ? <ChevronDown size={18} /> : <ChevronRight size={18} />}</span>
                          <div>
                            <h4 className="font-semibold text-slate-900">{student.student_name}</h4>
                            <p className="text-xs text-slate-500">
                              Admission: {student.admission_no || "-"}{student.roll_number ? ` · Roll: ${student.roll_number}` : ""}{student.student_email ? ` · ${student.student_email}` : ""}
                            </p>
                          </div>
                        </div>
                        <div>
                          <div className="mb-1 flex items-center justify-between text-xs text-slate-500">
                            <span>{student.completed_lessons}/{student.total_lessons} lessons completed</span>
                            <span className="font-semibold text-slate-700">{student.progress}%</span>
                          </div>
                          <ProgressBar value={student.progress} />
                        </div>
                        <div className="flex justify-start lg:justify-end">
                          <span className={`rounded-full px-2 py-1 text-xs font-semibold ${progressStatusClass(student.status)}`}>{progressStatusLabel(student.status)}</span>
                        </div>
                      </div>
                    </button>

                    {expandedStudentId === student.student_user_id && (
                      <div className="border-t border-slate-100 bg-slate-50 p-4">
                        <div className="mb-3 grid gap-2 text-xs text-slate-500 md:grid-cols-3">
                          <span>Enrolled: {formatDate(student.enrolled_at)}</span>
                          <span>Last activity: {formatDate(student.last_activity_at)}</span>
                          <span>Pending lessons: {student.pending_lessons}</span>
                        </div>
                        <div className="space-y-2">
                          {student.lessons.map((lesson) => (
                            <div key={lesson.lesson_id} className="flex flex-col gap-2 rounded-xl bg-white p-3 text-sm md:flex-row md:items-center md:justify-between">
                              <div className="min-w-0">
                                <p className="font-semibold text-slate-800">{lesson.order}. {lesson.title}</p>
                                <p className="text-xs text-slate-500">Completed: {lesson.completed_at ? formatDate(lesson.completed_at) : "-"}</p>
                              </div>
                              <div className="flex flex-wrap items-center gap-2">
                                {lesson.has_video && (
                                  <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-600">
                                    <Clock3 size={12} /> Watched {lesson.watch_percentage || 0}%
                                  </span>
                                )}
                                <span className={`inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs font-semibold ${lesson.completed ? "bg-green-50 text-green-700" : "bg-amber-50 text-amber-700"}`}>
                                  <CheckCircle2 size={12} /> {lesson.completed ? "Done" : "Pending"}
                                </span>
                              </div>
                            </div>
                          ))}
                          {student.lessons.length === 0 && <div className="rounded-xl bg-white p-3 text-sm text-slate-500">No lessons added yet.</div>}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
                {!loadingReport && reportStudents.length === 0 && <div className="rounded-2xl border border-dashed border-slate-200 bg-white p-6 text-center text-sm text-slate-500">No enrolled students found. Click Sync students after selecting class/section.</div>}
              </div>
            </div>

            <form id="lesson-form" onSubmit={saveLesson} className="mb-6 grid gap-4 md:grid-cols-4 scroll-mt-6">
              <div className="md:col-span-4 flex flex-col gap-2 rounded-2xl border border-slate-200 bg-slate-50 p-4 md:flex-row md:items-center md:justify-between">
                <div>
                  <h3 className="font-bold text-slate-900">{editingLesson ? "Edit lesson" : "Add lesson"}</h3>
                  <p className="text-sm text-slate-500">{editingLesson ? "Update the selected lesson title, order, description, files or video link." : "Create a new lesson for the selected course."}</p>
                </div>
                {editingLesson && (
                  <button type="button" onClick={resetLessonForm} className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100">
                    <X size={15} /> Cancel edit
                  </button>
                )}
              </div>
              <div className="md:col-span-2">
                <Label>Lesson title</Label>
                <Input value={lessonForm.title} required onChange={(e) => updateLesson("title", e.target.value)} />
              </div>
              <div>
                <Label>Order</Label>
                <Input type="number" value={lessonForm.order} onChange={(e) => updateLesson("order", e.target.value)} />
              </div>
              <div>
                <Label>Language</Label>
                <Input value={lessonForm.language} onChange={(e) => updateLesson("language", e.target.value)} />
              </div>
              <div className="md:col-span-4">
                <Label>Description</Label>
                <Textarea value={lessonForm.description} onChange={(e) => updateLesson("description", e.target.value)} />
              </div>
              <div className="md:col-span-2">
                <Label>External video link</Label>
                <Input value={lessonForm.external_video_link} placeholder="https://..." onChange={(e) => updateLesson("external_video_link", e.target.value)} />
              </div>
              <div>
                <Label>Video</Label>
                <input
                  className="block w-full text-sm text-slate-600"
                  type="file"
                  accept="video/mp4,video/webm,video/quicktime"
                  onChange={(e) => updateLesson("video", e.target.files?.[0] || null)}
                />
                {lessonForm.video && (
                  <p className="mt-1 text-xs text-slate-500">
                    Selected: {lessonForm.video.name} · {formatFileSize(lessonForm.video)}
                  </p>
                )}
              </div>
              <div>
                <Label>PDF</Label>
                <input
                  className="block w-full text-sm text-slate-600"
                  type="file"
                  accept="application/pdf"
                  onChange={(e) => updateLesson("pdf", e.target.files?.[0] || null)}
                />
                {lessonForm.pdf && (
                  <p className="mt-1 text-xs text-slate-500">
                    Selected: {lessonForm.pdf.name} · {formatFileSize(lessonForm.pdf)}
                  </p>
                )}
              </div>
              {lessonUploadProgress !== null && (
                <div className="md:col-span-4 rounded-2xl border border-violet-100 bg-violet-50 p-4">
                  <div className="mb-2 flex items-center justify-between text-sm">
                    <span className="font-semibold text-violet-800">{lessonUploadStatus || "Uploading..."}</span>
                    <span className="font-bold text-violet-800">{lessonUploadProgress}%</span>
                  </div>
                  <div className="h-3 overflow-hidden rounded-full bg-white">
                    <div className="h-full rounded-full bg-violet-600 transition-all" style={{ width: `${lessonUploadProgress}%` }} />
                  </div>
                  <p className="mt-2 text-xs text-violet-700">
                    For long videos, keep this tab open until the server confirms the lesson is saved.
                  </p>
                </div>
              )}
              <div className="md:col-span-4">
                <Button type="submit" disabled={savingLesson || !lessonForm.title}>{savingLesson ? (lessonUploadProgress !== null ? "Uploading..." : "Saving...") : editingLesson ? "Update Lesson" : "Add Lesson"}</Button>
              </div>
            </form>

            <div className="space-y-3">
              {lessons.map((lesson) => (
                <div key={lesson.id} className="rounded-2xl border border-slate-200 p-4">
                  <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                    <div>
                      <h3 className="font-semibold text-slate-900">{lesson.order}. {lesson.title}</h3>
                      <p className="mt-1 text-sm text-slate-500">{lesson.description || "No description"}</p>
                      <div className="mt-2 flex flex-wrap gap-2 text-sm">
                        {lesson.video_url && <a className="inline-flex items-center gap-1 rounded-xl bg-red-50 px-3 py-1 font-semibold text-red-700" href={fileUrl(lesson.video_url)} target="_blank"><PlayCircle size={14} /> Video</a>}
                        {lesson.external_video_link && <a className="inline-flex items-center gap-1 rounded-xl bg-red-50 px-3 py-1 font-semibold text-red-700" href={lesson.external_video_link} target="_blank"><PlayCircle size={14} /> Link</a>}
                        {lesson.pdf_url && <a className="inline-flex items-center gap-1 rounded-xl bg-blue-50 px-3 py-1 font-semibold text-blue-700" href={fileUrl(lesson.pdf_url)} target="_blank"><FileText size={14} /> PDF</a>}
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <button type="button" title="Edit lesson" onClick={() => startEditLesson(lesson)} className="rounded-xl border border-slate-200 p-2 text-slate-600 hover:bg-slate-100"><Edit2 size={16} /></button>
                      <button type="button" title="Delete lesson" onClick={() => deleteLesson(lesson)} className="rounded-xl border border-red-200 p-2 text-red-600 hover:bg-red-50"><Trash2 size={16} /></button>
                    </div>
                  </div>
                </div>
              ))}
              {lessons.length === 0 && <div className="rounded-2xl border border-dashed border-slate-200 p-6 text-center text-sm text-slate-500">No lessons have been added yet.</div>}
            </div>
          </>
        )}
      </Card>
    </AppSection>
  );
}

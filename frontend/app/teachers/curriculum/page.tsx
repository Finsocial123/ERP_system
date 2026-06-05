"use client";

import { useState, useMemo, useEffect } from "react";
import {
  NotebookIcon,
  Sparkles,
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  ArrowLeft,
  BookOpen,
  Clock,
  Users,
  Loader2,
  AlertCircle,
} from "lucide-react";

import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";
import LANGUAGES from "@/utils/languages";
import type { CourseMeta } from "@/types";

type LessonPlan = {
  title: string;
  description?: string;
  order: number;
};

type CurriculumPlan = {
  course_title: string;
  course_description: string;
  target_audience: string;
  duration_weeks: number;
  lessons: LessonPlan[];
};

type SuccessData = {
  message: string;
  course_id: number;
  course_title: string;
  lessons_created: number;
};

type Step = "form" | "preview" | "success";

function Label({ children }: { children: React.ReactNode }) {
  return (
    <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1.5">
      {children}
    </label>
  );
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="flex items-start gap-2.5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
      <AlertCircle size={16} className="mt-0.5 shrink-0 text-red-500" />
      {message}
    </div>
  );
}

function StatPill({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof BookOpen;
  label: string;
  value: string | number;
}) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
      <Icon size={14} className="text-slate-400" />
      <span className="text-slate-500">{label}</span>
      <span className="font-semibold text-slate-800">{value}</span>
    </div>
  );
}

function SelectField({
  value,
  onChange,
  disabled,
  children,
}: {
  value: string;
  onChange: (v: string) => void;
  disabled?: boolean;
  children: React.ReactNode;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      disabled={disabled}
      className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2.5 text-sm text-slate-900 outline-none transition focus:border-slate-400 focus:bg-white focus:ring-2 focus:ring-slate-100 disabled:opacity-50"
    >
      {children}
    </select>
  );
}

function GenerateForm({
  onGenerated,
}: {
  onGenerated: (plan: CurriculumPlan) => void;
}) {
  const [topic, setTopic] = useState("");
  const [audience, setAudience] = useState("");
  const [weeks, setWeeks] = useState(4);
  const [numLessons, setNumLessons] = useState(10);
  const [language, setLanguage] = useState("en");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canSubmit =
    topic.trim().length > 0 && audience.trim().length > 0 && !loading;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setLoading(true);
    setError(null);
    try {
      const plan = await apiFetch<CurriculumPlan>("/curriculum/generate", {
        method: "POST",
        body: JSON.stringify({
          topic,
          target_audience: audience,
          duration_weeks: weeks,
          num_lessons: numLessons,
          language,
        }),
      });
      onGenerated(plan);
    } catch (err: any) {
      setError(err.message ?? "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate>
      <div className="rounded-2xl border border-slate-200 bg-white">
        <div className="border-b border-slate-100 px-6 py-5">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-900">
              <Sparkles size={16} className="text-white" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-slate-900">
                Generate curriculum
              </h2>
              <p className="text-xs text-slate-500">
                Describe your course and let AI build the lesson plan
              </p>
            </div>
          </div>
        </div>

        <div className="space-y-5 px-6 py-6">
          <div>
            <Label>Course topic *</Label>
            <input
              type="text"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="e.g. Introduction to Algebra"
              disabled={loading}
              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2.5 text-sm text-slate-900 placeholder-slate-400 outline-none transition focus:border-slate-400 focus:bg-white focus:ring-2 focus:ring-slate-100 disabled:opacity-50"
            />
          </div>

          <div>
            <Label>Target audience *</Label>
            <input
              type="text"
              value={audience}
              onChange={(e) => setAudience(e.target.value)}
              placeholder="e.g. Grade 8 students with basic maths knowledge"
              disabled={loading}
              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2.5 text-sm text-slate-900 placeholder-slate-400 outline-none transition focus:border-slate-400 focus:bg-white focus:ring-2 focus:ring-slate-100 disabled:opacity-50"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>
                Duration — {weeks} week{weeks !== 1 ? "s" : ""}
              </Label>
              <input
                type="range"
                min={1}
                max={16}
                value={weeks}
                onChange={(e) => setWeeks(Number(e.target.value))}
                disabled={loading}
                className="mt-1 w-full accent-slate-900 disabled:opacity-50"
              />
              <div className="mt-1 flex justify-between text-xs text-slate-400">
                <span>1w</span>
                <span>16w</span>
              </div>
            </div>

            <div>
              <Label>Lessons — {numLessons}</Label>
              <input
                type="range"
                min={3}
                max={30}
                value={numLessons}
                onChange={(e) => setNumLessons(Number(e.target.value))}
                disabled={loading}
                className="mt-1 w-full accent-slate-900 disabled:opacity-50"
              />
              <div className="mt-1 flex justify-between text-xs text-slate-400">
                <span>3</span>
                <span>30</span>
              </div>
            </div>
          </div>

          <div>
            <Label>Language</Label>
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              disabled={loading}
              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2.5 text-sm text-slate-900 outline-none transition focus:border-slate-400 focus:bg-white focus:ring-2 focus:ring-slate-100 disabled:opacity-50"
            >
              {LANGUAGES.map((l) => (
                <option key={l.value} value={l.value}>
                  {l.label}
                </option>
              ))}
            </select>
          </div>

          {error && <ErrorBanner message={error} />}
        </div>

        <div className="border-t border-slate-100 px-6 py-4">
          <button
            type="submit"
            disabled={!canSubmit}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {loading ? (
              <>
                <Loader2 size={15} className="animate-spin" />
                Generating curriculum…
              </>
            ) : (
              <>
                <Sparkles size={15} />
                Generate curriculum
              </>
            )}
          </button>
        </div>
      </div>
    </form>
  );
}

function CurriculumPreview({
  plan,
  meta,
  onApproved,
  onBack,
}: {
  plan: CurriculumPlan;
  meta: CourseMeta;
  onApproved: (data: SuccessData) => void;
  onBack: () => void;
}) {
  const [draftPlan, setDraftPlan] = useState<CurriculumPlan>(plan);
  const [courseId, setCourseId] = useState("");
  const [classId, setClassId] = useState("");
  const [sectionId, setSectionId] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [expanded, setExpanded] = useState<number | null>(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setDraftPlan(plan);
  }, [plan]);

  function updateDraftLesson(index: number, key: keyof LessonPlan, value: string | number) {
    setDraftPlan((current) => ({
      ...current,
      lessons: current.lessons.map((lesson, i) =>
        i === index ? { ...lesson, [key]: value } : lesson,
      ),
    }));
  }

  const filteredSections = useMemo(() => {
    if (!classId) return [];
    return meta.sections.filter((s) => s.extra === classId);
  }, [classId, meta.sections]);

  async function handleApprove() {
    if (!classId) {
      setError("Please select a class before saving.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await apiFetch<SuccessData>("/curriculum/approve", {
        method: "POST",
        body: JSON.stringify({
          plan: draftPlan,
          course_id: courseId ? Number(courseId) : null,
          class_id: Number(classId),
          section_id: sectionId ? Number(sectionId) : null,
          subject_id: subjectId ? Number(subjectId) : null,
        }),
      });
      onApproved(result);
    } catch (err: any) {
      setError(err.message ?? "Approval failed. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <button
        type="button"
        onClick={onBack}
        className="flex items-center gap-1.5 text-sm font-medium text-slate-500 hover:text-slate-900 transition"
      >
        <ArrowLeft size={15} />
        Back to generator
      </button>

      <div className="rounded-2xl border border-slate-200 bg-white">
        {/* Course header */}
        <div className="border-b border-slate-100 px-6 py-5">
          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
            Generated curriculum
          </p>
          <h2 className="text-lg font-bold text-slate-900">
            {draftPlan.course_title}
          </h2>
          <p className="mt-1.5 text-sm text-slate-500 leading-relaxed">
            {draftPlan.course_description}
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <StatPill icon={Users} label="Audience" value={draftPlan.target_audience} />
            <StatPill icon={Clock} label="Duration" value={`${draftPlan.duration_weeks} weeks`} />
            <StatPill icon={BookOpen} label="Lessons" value={draftPlan.lessons.length} />
          </div>
        </div>

        {/* Lessons accordion */}
        <div className="divide-y divide-slate-100">
          {draftPlan.lessons.map((lesson, i) => {
            const isOpen = expanded === i;
            return (
              <div key={i} className="px-6 py-3.5 transition hover:bg-slate-50">
                <button
                  type="button"
                  onClick={() => setExpanded(isOpen ? null : i)}
                  className="flex w-full items-start gap-3 text-left"
                >
                  <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-slate-100 text-xs font-bold text-slate-500">
                    {lesson.order}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-800">
                      {lesson.title}
                    </p>
                    {isOpen && lesson.description && (
                      <p className="mt-1.5 text-xs text-slate-500 leading-relaxed">
                        {lesson.description}
                      </p>
                    )}
                  </div>
                  {isOpen ? (
                    <ChevronDown size={15} className="mt-0.5 shrink-0 text-slate-400" />
                  ) : (
                    <ChevronRight size={15} className="mt-0.5 shrink-0 text-slate-400" />
                  )}
                </button>
                {isOpen && (
                  <div className="mt-3 grid gap-3 rounded-xl border border-slate-200 bg-white p-3 md:grid-cols-[90px_1fr]">
                    <div>
                      <Label>Order</Label>
                      <input
                        type="number"
                        min={1}
                        value={lesson.order}
                        onChange={(e) => updateDraftLesson(i, "order", Number(e.target.value))}
                        disabled={loading}
                        className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm outline-none transition focus:border-slate-400 focus:bg-white"
                      />
                    </div>
                    <div>
                      <Label>Lesson title</Label>
                      <input
                        value={lesson.title}
                        onChange={(e) => updateDraftLesson(i, "title", e.target.value)}
                        disabled={loading}
                        className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm outline-none transition focus:border-slate-400 focus:bg-white"
                      />
                    </div>
                    <div className="md:col-span-2">
                      <Label>Description</Label>
                      <textarea
                        value={lesson.description || ""}
                        onChange={(e) => updateDraftLesson(i, "description", e.target.value)}
                        disabled={loading}
                        rows={3}
                        className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm outline-none transition focus:border-slate-400 focus:bg-white"
                      />
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Approve section */}
        <div className="border-t border-slate-100 px-6 py-5 space-y-4">
          <div>
            <p className="mb-3 text-sm font-semibold text-slate-700">
              Assign to class
            </p>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <Label>Class *</Label>
                <SelectField
                  value={classId}
                  onChange={(v) => { setClassId(v); setSectionId(""); }}
                  disabled={loading}
                >
                  <option value="">Select class</option>
                  {meta.classes.map((c) => (
                    <option key={c.id} value={String(c.id)}>{c.name}</option>
                  ))}
                </SelectField>
              </div>
              <div>
                <Label>Section</Label>
                <SelectField
                  value={sectionId}
                  onChange={setSectionId}
                  disabled={loading || !classId}
                >
                  <option value="">All sections</option>
                  {filteredSections.map((s) => (
                    <option key={s.id} value={String(s.id)}>{s.name}</option>
                  ))}
                </SelectField>
              </div>
              <div>
                <Label>Subject</Label>
                <SelectField
                  value={subjectId}
                  onChange={setSubjectId}
                  disabled={loading}
                >
                  <option value="">Select subject</option>
                  {meta.subjects.map((s) => (
                    <option key={s.id} value={String(s.id)}>{s.name}</option>
                  ))}
                </SelectField>
              </div>
            </div>
          </div>

          <div>
            <Label>Attach to existing course ID (optional)</Label>
            <input
              type="number"
              value={courseId}
              onChange={(e) => setCourseId(e.target.value)}
              placeholder="Leave blank to create a new course"
              min={1}
              disabled={loading}
              className="w-full max-w-xs rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2.5 text-sm text-slate-900 placeholder-slate-400 outline-none transition focus:border-slate-400 focus:bg-white focus:ring-2 focus:ring-slate-100 disabled:opacity-50"
            />
          </div>

          {error && <ErrorBanner message={error} />}

          <button
            type="button"
            onClick={handleApprove}
            disabled={loading}
            className="flex items-center justify-center gap-2 rounded-xl bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {loading ? (
              <>
                <Loader2 size={15} className="animate-spin" />
                Saving…
              </>
            ) : (
              <>
                <CheckCircle2 size={15} />
                Approve &amp; save curriculum
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

function SuccessBanner({
  data,
  onReset,
}: {
  data: SuccessData;
  onReset: () => void;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white">
      <div className="flex flex-col items-center gap-4 px-8 py-12 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-emerald-50 border border-emerald-200">
          <CheckCircle2 size={28} className="text-emerald-600" />
        </div>
        <div>
          <h2 className="text-lg font-bold text-slate-900">Curriculum saved!</h2>
          <p className="mt-1 text-sm text-slate-500">{data.message}</p>
        </div>

        <div className="w-full max-w-sm rounded-xl border border-slate-100 bg-slate-50 divide-y divide-slate-100 text-left">
          <div className="px-4 py-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-0.5">
              Course
            </p>
            <p className="text-sm font-semibold text-slate-800">{data.course_title}</p>
          </div>
          <div className="grid grid-cols-2 divide-x divide-slate-100">
            <div className="px-4 py-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-0.5">
                Course ID
              </p>
              <p className="font-mono text-sm font-semibold text-slate-800">
                #{data.course_id}
              </p>
            </div>
            <div className="px-4 py-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-0.5">
                Lessons
              </p>
              <p className="text-sm font-semibold text-slate-800">
                {data.lessons_created} created
              </p>
            </div>
          </div>
        </div>

        <button
          type="button"
          onClick={onReset}
          className="mt-2 flex items-center gap-2 rounded-xl border border-slate-200 px-5 py-2.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-100"
        >
          <Sparkles size={14} />
          Generate another curriculum
        </button>
      </div>
    </div>
  );
}

export default function CurriculumPage() {
  const [step, setStep] = useState<Step>("form");
  const [plan, setPlan] = useState<CurriculumPlan | null>(null);
  const [successData, setSuccessData] = useState<SuccessData | null>(null);
  const [meta, setMeta] = useState<CourseMeta | null>(null);

  useEffect(() => {
    apiFetch<CourseMeta>("/courses/meta").then(setMeta).catch(() => {});
  }, []);

  function handleGenerated(p: CurriculumPlan) {
    setPlan(p);
    setStep("preview");
  }

  function handleApproved(d: SuccessData) {
    setSuccessData(d);
    setStep("success");
  }

  function handleReset() {
    setPlan(null);
    setSuccessData(null);
    setStep("form");
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-2xl space-y-6">
        <div className="flex items-center gap-3">
          <NotebookIcon size={22} className="text-slate-400" />
          <div>
            <h1 className="text-xl font-bold text-slate-900">AI Curriculum</h1>
            <p className="text-xs text-slate-500">
              Generate and save a complete lesson plan for your course
            </p>
          </div>
        </div>

        {step === "form" && <GenerateForm onGenerated={handleGenerated} />}

        {step === "preview" && plan && meta && (
          <CurriculumPreview
            plan={plan}
            meta={meta}
            onApproved={handleApproved}
            onBack={handleReset}
          />
        )}

        {step === "preview" && plan && !meta && (
          <div className="flex items-center justify-center py-12 text-sm text-slate-500">
            <Loader2 size={16} className="mr-2 animate-spin" />
            Loading class data…
          </div>
        )}

        {step === "success" && successData && (
          <SuccessBanner data={successData} onReset={handleReset} />
        )}
      </div>
    </AppShell>
  );
}
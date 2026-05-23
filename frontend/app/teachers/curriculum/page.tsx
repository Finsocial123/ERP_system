"use client";

import { useState, useMemo } from "react";
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
  Hash,
  Globe,
  Loader2,
  AlertCircle,
} from "lucide-react";

import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";
import LANGUAGES from "@/utils/languages";

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
        {/* Header */}
        <div className="border-b border-slate-100 px-6 py-5">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-900">
              <Sparkles size={16} className="text-white" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-slate-900">
                Generate Curriculum
              </h2>
              <p className="text-xs text-slate-500">
                Describe your course and let AI build the lesson plan
              </p>
            </div>
          </div>
        </div>

        {/* Fields */}
        <div className="space-y-5 px-6 py-6">
          {/* Topic */}
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

          {/* Audience */}
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

          {/* Duration + Lessons side by side */}
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

          {/* Language */}
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

        {/* Footer */}
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
  onApproved,
  onBack,
}: {
  plan: CurriculumPlan;
  onApproved: (data: SuccessData) => void;
  onBack: () => void;
}) {
  const [courseId, setCourseId] = useState("");
  const [expanded, setExpanded] = useState<number | null>(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleApprove() {
    setLoading(true);
    setError(null);
    try {
      const result = await apiFetch<SuccessData>("/curriculum/approve", {
        method: "POST",
        body: JSON.stringify({
          plan,
          course_id: courseId ? Number(courseId) : null,
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

      {/* Course card */}
      <div className="rounded-2xl border border-slate-200 bg-white">
        <div className="border-b border-slate-100 px-6 py-5">
          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
            Generated curriculum
          </p>
          <h2 className="text-lg font-bold text-slate-900">
            {plan.course_title}
          </h2>
          <p className="mt-1.5 text-sm text-slate-500 leading-relaxed">
            {plan.course_description}
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <StatPill
              icon={Users}
              label="Audience"
              value={plan.target_audience}
            />
            <StatPill
              icon={Clock}
              label="Duration"
              value={`${plan.duration_weeks} weeks`}
            />
            <StatPill
              icon={BookOpen}
              label="Lessons"
              value={plan.lessons.length}
            />
          </div>
        </div>

        {/* Lessons accordion */}
        <div className="divide-y divide-slate-100">
          {plan.lessons.map((lesson, i) => {
            const isOpen = expanded === i;
            return (
              <button
                key={i}
                type="button"
                onClick={() => setExpanded(isOpen ? null : i)}
                className="flex w-full items-start gap-3 px-6 py-3.5 text-left transition hover:bg-slate-50"
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
                  <ChevronDown
                    size={15}
                    className="mt-0.5 shrink-0 text-slate-400"
                  />
                ) : (
                  <ChevronRight
                    size={15}
                    className="mt-0.5 shrink-0 text-slate-400"
                  />
                )}
              </button>
            );
          })}
        </div>

        {/* Approve section */}
        <div className="border-t border-slate-100 px-6 py-5 space-y-4">
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
          <h2 className="text-lg font-bold text-slate-900">
            Curriculum saved!
          </h2>
          <p className="mt-1 text-sm text-slate-500">{data.message}</p>
        </div>

        <div className="w-full max-w-sm rounded-xl border border-slate-100 bg-slate-50 divide-y divide-slate-100 text-left">
          <div className="px-4 py-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-0.5">
              Course
            </p>
            <p className="text-sm font-semibold text-slate-800">
              {data.course_title}
            </p>
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

        {step === "preview" && plan && (
          <CurriculumPreview
            plan={plan}
            onApproved={handleApproved}
            onBack={handleReset}
          />
        )}

        {step === "success" && successData && (
          <SuccessBanner data={successData} onReset={handleReset} />
        )}
      </div>
    </AppShell>
  );
}

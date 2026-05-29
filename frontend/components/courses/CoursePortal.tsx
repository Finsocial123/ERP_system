"use client";

import { useEffect, useMemo, useState } from "react";
import type React from "react";
import { CheckCircle2, FileText, PlayCircle, RefreshCcw } from "lucide-react";

import { AppSection } from "@/components/CrudManager";
import { Button, Card, Input } from "@/components/ui";
import { apiFetch, fileUrl } from "@/lib/api";
import type { CourseProgress, LMSCourse, LMSLesson } from "@/types";

type Props = {
  mode: "student" | "parent";
};

function progressClass(value?: number | null) {
  const progress = Number(value || 0);
  if (progress >= 80) return "bg-green-50 text-green-700";
  if (progress >= 40) return "bg-amber-50 text-amber-700";
  return "bg-slate-100 text-slate-700";
}

export default function CoursePortal({ mode }: Props) {
  const [courses, setCourses] = useState<LMSCourse[]>([]);
  const [selected, setSelected] = useState<LMSCourse | null>(null);
  const [lessons, setLessons] = useState<LMSLesson[]>([]);
  const [progress, setProgress] = useState<CourseProgress | null>(null);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const loadCourses = async () => {
    setLoading(true);
    setError("");
    try {
      const path = mode === "student" ? "/courses/student/my" : "/courses/parent/children";
      const rows = await apiFetch<LMSCourse[]>(path);
      setCourses(rows);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load courses");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCourses();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  const loadLessons = async (course: LMSCourse) => {
    setSelected(course);
    setError("");
    setSuccess("");
    try {
      const lessonRows = await apiFetch<LMSLesson[]>(`/lessons/course/${course.id}`);
      setLessons(lessonRows);
      if (mode === "student") {
        const progressData = await apiFetch<CourseProgress>(`/progress/course/${course.id}`);
        setProgress(progressData);
      } else {
        setProgress(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load lessons");
    }
  };

  const completedMap = useMemo(() => {
    const map: Record<number, boolean> = {};
    progress?.lessons.forEach((item) => {
      map[item.lesson_id] = item.completed;
    });
    return map;
  }, [progress]);

  const markComplete = async (lesson: LMSLesson) => {
    setError("");
    setSuccess("");
    try {
      await apiFetch(`/progress/${lesson.id}/complete`, { method: "POST" });
      setSuccess("Lesson marked as complete");
      if (selected) await loadLessons(selected);
      await loadCourses();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update progress");
    }
  };

  const trackVideo = async (lesson: LMSLesson, event: React.SyntheticEvent<HTMLVideoElement>) => {
    if (mode !== "student") return;
    const video = event.currentTarget;
    if (!video.duration || video.paused) return;
    try {
      await apiFetch(`/progress/${lesson.id}/watch`, {
        method: "POST",
        body: JSON.stringify({
          watched_seconds_delta: 5,
          video_duration_seconds: video.duration,
          current_position_seconds: video.currentTime,
        }),
      });
    } catch {
      // Progress pings should not interrupt the student while watching.
    }
  };

  const visibleCourses = courses.filter((course) => {
    if (!search.trim()) return true;
    const query = search.toLowerCase();
    return [course.title, course.class_name, course.section_name, course.subject_name, course.teacher_name, course.student_name]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(query));
  });

  return (
    <AppSection
      title={mode === "student" ? "My Courses" : "Child Courses"}
      description={mode === "student" ? "View assigned class courses, open PDFs/videos, and track lesson completion." : "View the courses assigned to your children based on their class and section."}
    >
      <div className="grid gap-6 xl:grid-cols-[0.85fr_1.15fr]">
        <Card>
          <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
            <div>
              <h2 className="text-lg font-bold text-slate-900">Courses</h2>
              <p className="text-sm text-slate-500">{loading ? "Loading..." : `${visibleCourses.length} course(s)`}</p>
            </div>
            <div className="flex gap-2">
              <Input placeholder="Search" value={search} onChange={(e) => setSearch(e.target.value)} />
              <button type="button" onClick={loadCourses} className="rounded-xl border border-slate-200 p-2 text-slate-700 hover:bg-slate-100"><RefreshCcw size={18} /></button>
            </div>
          </div>

          {error && <div className="mb-4 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
          {success && <div className="mb-4 rounded-xl bg-green-50 px-4 py-3 text-sm text-green-700">{success}</div>}

          <div className="space-y-3">
            {visibleCourses.map((course, index) => (
              <button
                key={`${course.id}-${course.student_id || index}`}
                onClick={() => loadLessons(course)}
                className={`w-full rounded-2xl border p-4 text-left transition ${selected?.id === course.id && selected?.student_id === course.student_id ? "border-slate-900 bg-slate-50" : "border-slate-200 hover:bg-slate-50"}`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="font-bold text-slate-900">{course.title}</h3>
                    <p className="mt-1 text-sm text-slate-500">{course.class_name || "-"}{course.section_name ? ` · ${course.section_name}` : " · All sections"}{course.subject_name ? ` · ${course.subject_name}` : ""}</p>
                    {mode === "parent" && <p className="mt-1 text-sm text-slate-500">Child: {course.student_name || "-"} {course.admission_no ? `(${course.admission_no})` : ""}</p>}
                    <p className="mt-1 text-sm text-slate-500">Teacher: {course.teacher_name || "-"} · Lessons: {course.lessons_count}</p>
                  </div>
                  <span className={`rounded-full px-2 py-1 text-xs font-semibold ${progressClass(course.progress)}`}>{Math.round(Number(course.progress || 0))}%</span>
                </div>
              </button>
            ))}
            {!loading && visibleCourses.length === 0 && <div className="rounded-2xl border border-dashed border-slate-200 p-6 text-center text-sm text-slate-500">No courses assigned yet.</div>}
          </div>
        </Card>

        <Card>
          {!selected ? (
            <div className="rounded-2xl border border-dashed border-slate-200 p-8 text-center text-slate-500">Select a course to view lessons.</div>
          ) : (
            <>
              <div className="mb-4 flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                <div>
                  <h2 className="text-lg font-bold text-slate-900">{selected.title}</h2>
                  <p className="text-sm text-slate-500">{selected.class_name}{selected.section_name ? ` · ${selected.section_name}` : " · All sections"}{selected.subject_name ? ` · ${selected.subject_name}` : ""}</p>
                </div>
                <span className={`rounded-full px-3 py-1 text-sm font-semibold ${progressClass(mode === "student" ? progress?.overall_progress : selected.progress)}`}>{Math.round(Number(mode === "student" ? progress?.overall_progress || 0 : selected.progress || 0))}% complete</span>
              </div>

              <div className="space-y-4">
                {lessons.map((lesson) => {
                  const completed = completedMap[lesson.id];
                  return (
                    <div key={lesson.id} className="rounded-2xl border border-slate-200 p-4">
                      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <h3 className="font-semibold text-slate-900">{lesson.order}. {lesson.title}</h3>
                            {completed && <span className="rounded-full bg-green-50 px-2 py-1 text-xs font-semibold text-green-700"><CheckCircle2 size={12} className="mr-1 inline" />Completed</span>}
                          </div>
                          <p className="mt-1 text-sm text-slate-500">{lesson.description || "No description"}</p>
                        </div>
                        {mode === "student" && (
                          <Button type="button" onClick={() => markComplete(lesson)} disabled={completed}>{completed ? "Completed" : "Mark Complete"}</Button>
                        )}
                      </div>

                      <div className="mt-3 space-y-3">
                        {lesson.video_url && (
                          <video className="w-full rounded-2xl border border-slate-200" controls src={fileUrl(lesson.video_url)} onTimeUpdate={(event) => trackVideo(lesson, event)} />
                        )}
                        {lesson.external_video_link && !lesson.video_url && (
                          <a className="inline-flex items-center gap-2 rounded-xl bg-red-50 px-3 py-2 text-sm font-semibold text-red-700" href={lesson.external_video_link} target="_blank"><PlayCircle size={16} /> Open video link</a>
                        )}
                        {lesson.pdf_url && (
                          <a className="inline-flex items-center gap-2 rounded-xl bg-blue-50 px-3 py-2 text-sm font-semibold text-blue-700" href={fileUrl(lesson.pdf_url)} target="_blank"><FileText size={16} /> Open PDF</a>
                        )}
                      </div>
                    </div>
                  );
                })}
                {lessons.length === 0 && <div className="rounded-2xl border border-dashed border-slate-200 p-6 text-center text-sm text-slate-500">No lessons have been added yet.</div>}
              </div>
            </>
          )}
        </Card>
      </div>
    </AppSection>
  );
}

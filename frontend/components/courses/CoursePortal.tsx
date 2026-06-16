"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type React from "react";
import {
  BookOpen,
  CheckCircle2,
  ChevronRight,
  FileText,
  Layers,
  PlayCircle,
  RefreshCcw,
  Search,
  User,
  MessageCircle,
  ClipboardList,
  BookMarked,
} from "lucide-react";

import CourseLessonChat from "@/components/courses/CourseLessonChat";
import LessonQuizGenerator from "@/components/courses/LessonQuizGenerator";
import LessonSummaryGenerator from "@/components/courses/LessonSummaryGenerator";
import { apiFetch, fileUrl } from "@/lib/api";
import type { CourseProgress, LMSCourse, LMSLesson } from "@/types";

type Props = { mode: "student" | "parent" };
type AITab = "chat" | "quiz" | "summary";

function progressColor(v?: number | null) {
  const p = Number(v || 0);
  if (p >= 80) return { bar: "#10b981", text: "#065f46", bg: "#d1fae5" };
  if (p >= 40) return { bar: "#f59e0b", text: "#78350f", bg: "#fef3c7" };
  return { bar: "#94a3b8", text: "#475569", bg: "#f1f5f9" };
}

function ProgressBar({ value, h = 4 }: { value: number; h?: number }) {
  const { bar } = progressColor(value);
  return (
    <div style={{ background: "#e2e8f0", borderRadius: 999, height: h, overflow: "hidden", width: "100%" }}>
      <div style={{ height: "100%", width: `${Math.min(100, Math.max(0, value))}%`, background: bar, borderRadius: 999, transition: "width 0.5s ease" }} />
    </div>
  );
}

type WatchStatus = {
  watched_seconds: number;
  video_duration_seconds: number;
  required_watch_seconds: number;
  watch_percentage: number;
  required_watch_percentage?: number;
  requirement_progress_percentage?: number;
  can_mark_complete: boolean;
};

type WatchStatusInput = Partial<WatchStatus> | null | undefined;

const VIDEO_REQUIRED_RATIO = 0.75;
const WATCH_TICK_MS = 1000;
const WATCH_FLUSH_INTERVAL_MS = 5000;
const WATCH_MIN_FLUSH_SECONDS = 3;

function normalizeWatchStatus(status?: WatchStatusInput): WatchStatus {
  const duration = Number(status?.video_duration_seconds || 0);
  const watched = Number(status?.watched_seconds || 0);
  const required = Number(status?.required_watch_seconds || (duration > 0 ? duration * VIDEO_REQUIRED_RATIO : 0));
  const safeDuration = Math.max(duration, 0);
  const safeRequired = Math.max(required, 0);
  const safeWatched = Math.min(Math.max(watched, 0), safeDuration || watched);
  return {
    watched_seconds: Math.round(safeWatched * 100) / 100,
    video_duration_seconds: Math.round(safeDuration * 100) / 100,
    required_watch_seconds: Math.round(safeRequired * 100) / 100,
    // This is the actual percent of the whole video, shown as "Watched X%".
    watch_percentage: safeDuration > 0
      ? Math.round(Math.min((safeWatched / safeDuration) * 100, 100) * 100) / 100
      : Number(status?.watch_percentage || 0),
    required_watch_percentage: Number(status?.required_watch_percentage || VIDEO_REQUIRED_RATIO * 100),
    requirement_progress_percentage: safeRequired > 0
      ? Math.round(Math.min((safeWatched / safeRequired) * 100, 100) * 100) / 100
      : Number(status?.requirement_progress_percentage || 0),
    can_mark_complete: Boolean(status?.can_mark_complete || (safeRequired > 0 && safeWatched >= safeRequired)),
  };
}

function buildLocalWatchStatus(base: WatchStatus, watchedSeconds: number, durationSeconds: number): WatchStatus {
  const duration = Math.max(durationSeconds || base.video_duration_seconds || 0, 0);
  const required = duration > 0 ? Math.round(duration * VIDEO_REQUIRED_RATIO * 100) / 100 : base.required_watch_seconds;
  const watched = Math.round(Math.min(Math.max(watchedSeconds, 0), duration || watchedSeconds) * 100) / 100;
  return {
    watched_seconds: watched,
    video_duration_seconds: duration ? Math.round(duration * 100) / 100 : base.video_duration_seconds,
    required_watch_seconds: required,
    watch_percentage: duration > 0 ? Math.round(Math.min((watched / duration) * 100, 100) * 100) / 100 : 0,
    required_watch_percentage: VIDEO_REQUIRED_RATIO * 100,
    requirement_progress_percentage: required > 0 ? Math.round(Math.min((watched / required) * 100, 100) * 100) / 100 : 0,
    can_mark_complete: required > 0 && watched >= required,
  };
}

function OptimizedVideoPlayer({
  lesson,
  mode,
  initialStatus,
  onStatusSynced,
  onRegisterFlush,
}: {
  lesson: LMSLesson;
  mode: "student" | "parent";
  initialStatus?: WatchStatusInput;
  onStatusSynced?: (lessonId: number, status: WatchStatus) => void;
  onRegisterFlush?: (lessonId: number, flushFn?: () => Promise<WatchStatus | null>) => void;
}) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const timerRef = useRef<number | null>(null);
  const pendingSecondsRef = useRef(0);
  const lastTickAtRef = useRef<number | null>(null);
  const lastFlushAtRef = useRef<number>(Date.now());
  const inFlightRef = useRef(false);
  const statusRef = useRef<WatchStatus>(normalizeWatchStatus(initialStatus));
  const [localStatus, setLocalStatus] = useState<WatchStatus>(() => statusRef.current);

  useEffect(() => {
    const nextStatus = normalizeWatchStatus(initialStatus);
    pendingSecondsRef.current = 0;
    lastTickAtRef.current = null;
    lastFlushAtRef.current = Date.now();
    inFlightRef.current = false;
    statusRef.current = nextStatus;
    setLocalStatus(nextStatus);
    // Reset only when the lesson changes. Parent progress updates every second for UI,
    // but those updates should not reset the unsaved local watch accumulator.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lesson.id]);

  const stopTimer = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
    lastTickAtRef.current = null;
  }, []);

  const mergeLocalStatus = useCallback((deltaSeconds: number, video: HTMLVideoElement) => {
    const duration = Number.isFinite(video.duration) ? video.duration : 0;
    const current = statusRef.current;
    const next = buildLocalWatchStatus(current, (current.watched_seconds || 0) + deltaSeconds, duration);
    statusRef.current = next;
    setLocalStatus(next);
    onStatusSynced?.(lesson.id, next);
  }, [lesson.id, onStatusSynced]);

  const applySyncedStatus = useCallback((status: WatchStatusInput) => {
    const normalized = normalizeWatchStatus(status);
    statusRef.current = normalized;
    setLocalStatus(normalized);
    onStatusSynced?.(lesson.id, normalized);
    return normalized;
  }, [lesson.id, onStatusSynced]);

  const flushWatchProgress = useCallback(async (video: HTMLVideoElement, force = false): Promise<WatchStatus | null> => {
    if (mode !== "student" || !lesson.video_url) return null;
    if (inFlightRef.current) {
      for (let i = 0; i < 25 && inFlightRef.current; i += 1) {
        await new Promise<void>((resolve) => window.setTimeout(resolve, 100));
      }
      if (inFlightRef.current) return statusRef.current;
    }

    const pending = Math.round(pendingSecondsRef.current * 100) / 100;
    const duration = Number.isFinite(video.duration) ? video.duration : 0;
    const position = Number.isFinite(video.currentTime) ? video.currentTime : 0;

    if (pending <= 0 || (!force && pending < WATCH_MIN_FLUSH_SECONDS)) {
      const status = await apiFetch<WatchStatus>(`/progress/${lesson.id}/watch`);
      return applySyncedStatus(status);
    }

    pendingSecondsRef.current = 0;
    inFlightRef.current = true;

    try {
      const status = await apiFetch<WatchStatus>(`/progress/${lesson.id}/watch`, {
        method: "POST",
        body: JSON.stringify({
          watched_seconds_delta: pending,
          video_duration_seconds: duration,
          current_position_seconds: position,
        }),
      });
      lastFlushAtRef.current = Date.now();
      return applySyncedStatus(status);
    } catch {
      // Non-blocking progress save. Put the unsaved seconds back and retry on the next flush.
      pendingSecondsRef.current += pending;
      return null;
    } finally {
      inFlightRef.current = false;
    }
  }, [applySyncedStatus, lesson.id, lesson.video_url, mode]);

  const startTimer = useCallback(() => {
    if (mode !== "student" || !lesson.video_url || timerRef.current !== null) return;
    const video = videoRef.current;
    if (!video) return;

    lastTickAtRef.current = Date.now();
    timerRef.current = window.setInterval(() => {
      const currentVideo = videoRef.current;
      if (!currentVideo || currentVideo.paused || currentVideo.ended) {
        lastTickAtRef.current = Date.now();
        return;
      }

      const now = Date.now();
      const lastTick = lastTickAtRef.current || now;
      const elapsed = Math.min(Math.max((now - lastTick) / 1000, 0), 2);
      lastTickAtRef.current = now;

      if (elapsed <= 0) return;
      pendingSecondsRef.current += elapsed;
      mergeLocalStatus(elapsed, currentVideo);

      const shouldFlush =
        now - lastFlushAtRef.current >= WATCH_FLUSH_INTERVAL_MS &&
        pendingSecondsRef.current >= WATCH_MIN_FLUSH_SECONDS;

      if (shouldFlush) {
        void flushWatchProgress(currentVideo, false);
      }
    }, WATCH_TICK_MS);
  }, [flushWatchProgress, lesson.video_url, mergeLocalStatus, mode]);

  const flushAndStop = useCallback((video: HTMLVideoElement) => {
    stopTimer();
    void flushWatchProgress(video, true);
  }, [flushWatchProgress, stopTimer]);

  useEffect(() => {
    if (!onRegisterFlush) return undefined;

    onRegisterFlush(lesson.id, async () => {
      const video = videoRef.current;
      if (video) {
        return flushWatchProgress(video, true);
      }

      const status = await apiFetch<WatchStatus>(`/progress/${lesson.id}/watch`);
      return applySyncedStatus(status);
    });

    return () => onRegisterFlush(lesson.id, undefined);
  }, [applySyncedStatus, flushWatchProgress, lesson.id, onRegisterFlush]);

  useEffect(() => {
    const handleVisibilityChange = () => {
      const video = videoRef.current;
      if (document.visibilityState === "hidden" && video) {
        flushAndStop(video);
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      const video = videoRef.current;
      stopTimer();
      if (video) {
        void flushWatchProgress(video, true);
      }
    };
  }, [flushAndStop, flushWatchProgress, stopTimer]);

  const showWatchProgress = mode === "student" && Boolean(lesson.video_url);

  return (
    <div>
      <div className="cp-video-wrap">
        <video
          ref={videoRef}
          key={lesson.id}
          controls
          src={fileUrl(lesson.video_url)}
          onLoadedMetadata={(event) => {
            const video = event.currentTarget;
            const duration = Number.isFinite(video.duration) ? video.duration : 0;
            const current = statusRef.current;
            const next = buildLocalWatchStatus(current, current.watched_seconds, duration);
            statusRef.current = next;
            setLocalStatus(next);
            onStatusSynced?.(lesson.id, next);
          }}
          onPlay={startTimer}
          onPause={(event) => flushAndStop(event.currentTarget)}
          onEnded={(event) => flushAndStop(event.currentTarget)}
        />
      </div>
      {showWatchProgress && (
        <div style={{ marginTop: 8, display: "flex", alignItems: "center", gap: 10, fontSize: "0.72rem", color: "#64748b" }}>
          <div style={{ flex: 1 }}>
            <ProgressBar value={localStatus.watch_percentage} h={4} />
          </div>
          <span style={{ whiteSpace: "nowrap", fontWeight: 600 }}>
            Watched {Math.round(localStatus.watch_percentage)}%
          </span>
        </div>
      )}
    </div>
  );
}

export default function CoursePortal({ mode }: Props) {
  const [courses, setCourses] = useState<LMSCourse[]>([]);
  const [selected, setSelected] = useState<LMSCourse | null>(null);
  const [activeLesson, setActiveLesson] = useState<LMSLesson | null>(null);
  const [lessons, setLessons] = useState<LMSLesson[]>([]);
  const [progress, setProgress] = useState<CourseProgress | null>(null);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [aiTab, setAiTab] = useState<AITab>("chat");
  // Track aiTab key per lesson so components remount on lesson change
  const [aiKey, setAiKey] = useState(0);
  const lessonFlushersRef = useRef<Record<number, () => Promise<WatchStatus | null>>>({});

  const registerLessonFlusher = useCallback((lessonId: number, flushFn?: () => Promise<WatchStatus | null>) => {
    if (flushFn) {
      lessonFlushersRef.current[lessonId] = flushFn;
    } else {
      delete lessonFlushersRef.current[lessonId];
    }
  }, []);

  const loadCourses = async () => {
    setLoading(true); setError("");
    try {
      const path = mode === "student" ? "/courses/student/my" : "/courses/parent/children";
      setCourses(await apiFetch<LMSCourse[]>(path));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load courses");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadCourses(); }, [mode]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadLessons = async (course: LMSCourse) => {
    setSelected(course); setActiveLesson(null); setError(""); setSuccess("");
    try {
      const rows = await apiFetch<LMSLesson[]>(`/lessons/course/${course.id}`);
      setLessons(rows);
      setProgress(mode === "student" ? await apiFetch<CourseProgress>(`/progress/course/${course.id}`) : null);
      if (rows.length > 0) { setActiveLesson(rows[0]); setAiKey((k) => k + 1); }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load lessons");
    }
  };

  const completedMap = useMemo(() => {
    const map: Record<number, boolean> = {};
    progress?.lessons.forEach((item) => { map[item.lesson_id] = item.completed; });
    return map;
  }, [progress]);

  const markComplete = async (lesson: LMSLesson) => {
    setError(""); setSuccess("");
    try {
      // Before completing, force-save the latest watched seconds from the video player.
      // This prevents the UI from showing enough progress while the backend still has older data.
      const flushBeforeComplete = lessonFlushersRef.current[lesson.id];
      const syncedStatus = lesson.video_url && flushBeforeComplete ? await flushBeforeComplete() : null;

      if (lesson.video_url && syncedStatus && !syncedStatus.can_mark_complete) {
        const requiredPercent = Math.round(syncedStatus.required_watch_percentage || VIDEO_REQUIRED_RATIO * 100);
        const watchedPercent = Math.round(syncedStatus.watch_percentage || 0);
        const remainingSeconds = Math.max(
          Math.ceil((syncedStatus.required_watch_seconds || 0) - (syncedStatus.watched_seconds || 0)),
          0,
        );
        setError(`Please watch at least ${requiredPercent}% of this video before marking complete. Current saved watch is ${watchedPercent}%. Watch about ${remainingSeconds} more seconds.`);
        return;
      }

      await apiFetch(`/progress/${lesson.id}/complete`, { method: "POST" });
      setSuccess("Lesson marked as complete!");
      if (selected) await loadLessons(selected);
      await loadCourses();
      setTimeout(() => setSuccess(""), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update progress");
    }
  };

  const selectLesson = (lesson: LMSLesson) => {
    setActiveLesson(lesson);
    setAiKey((k) => k + 1);
  };

  const visibleCourses = courses.filter((c) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return [c.title, c.class_name, c.section_name, c.subject_name, c.teacher_name, c.student_name]
      .filter(Boolean).some((v) => String(v).toLowerCase().includes(q));
  });

  const overallProgress = Math.round(Number(mode === "student" ? progress?.overall_progress || 0 : selected?.progress || 0));
  const completedCount = lessons.filter((l) => completedMap[l.id]).length;

  const activeLessonProgress = useMemo(() => (
    activeLesson ? progress?.lessons.find((item) => item.lesson_id === activeLesson.id) : undefined
  ), [activeLesson, progress]);

  const updateLessonWatchStatus = useCallback((lessonId: number, status: WatchStatus) => {
    setProgress((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        lessons: prev.lessons.map((item) => (
          item.lesson_id === lessonId
            ? {
              ...item,
              watched_seconds: status.watched_seconds,
              video_duration_seconds: status.video_duration_seconds,
              required_watch_seconds: status.required_watch_seconds,
              watch_percentage: status.watch_percentage,
              required_watch_percentage: status.required_watch_percentage,
              requirement_progress_percentage: status.requirement_progress_percentage,
              can_mark_complete: item.completed || status.can_mark_complete,
            }
            : item
        )),
      };
    });
  }, []);

  const aiTabs: { id: AITab; label: string; icon: React.ComponentType<{ size?: number; color?: string }>; accent: string; lightBg: string; activeBg: string; activeFg: string }[] = [
    { id: "chat", label: "AI Chat", icon: MessageCircle, accent: "#7c3aed", lightBg: "#ede9fe", activeBg: "#7c3aed", activeFg: "#ffffff" },
    { id: "quiz", label: "Quiz", icon: ClipboardList, accent: "#2563eb", lightBg: "#eff6ff", activeBg: "#2563eb", activeFg: "#ffffff" },
    { id: "summary", label: "Summary", icon: BookMarked, accent: "#d97706", lightBg: "#fffbeb", activeBg: "#d97706", activeFg: "#ffffff" },
  ];

  return (
    <>
      <style>{`
        .cp { font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; }
        .cp * { box-sizing: border-box; }

        /* ── 3-panel grid ── */
        .cp-grid {
          display: grid;
          grid-template-columns: 286px 1fr 340px;
          gap: 16px;
          align-items: start;
        }
        @media (max-width: 1280px) {
          .cp-grid { grid-template-columns: 260px 1fr 310px; }
        }
        @media (max-width: 1023px) {
          .cp-grid { grid-template-columns: 1fr; }
          .cp-ai-rail { position: static !important; }
        }

        /* ── Shared card ── */
        .cp-card {
          background: #fff;
          border: 1px solid #e2e8f0;
          border-radius: 14px;
          overflow: hidden;
          box-shadow: 0 1px 3px rgba(0,0,0,0.06);
        }

        /* ── Left: course sidebar ── */
        .cp-course-panel {
          position: sticky;
          top: 16px;
          max-height: calc(100vh - 88px);
          display: flex;
          flex-direction: column;
          overflow: hidden;
        }
        .cp-course-head {
          flex-shrink: 0;
          padding: 14px 14px 10px;
          border-bottom: 1px solid #e2e8f0;
        }
        .cp-course-list {
          flex: 1;
          min-height: 0;
          overflow-y: auto;
          padding: 8px;
          scrollbar-width: thin;
          scrollbar-color: #cbd5e1 transparent;
        }
        .cp-course-list::-webkit-scrollbar { width: 4px; }
        .cp-course-list::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 99px; }

        /* course card button */
        .cp-course-btn {
          width: 100%;
          text-align: left;
          border: 1px solid #e2e8f0;
          border-radius: 12px;
          padding: 11px 12px;
          cursor: pointer;
          background: none;
          transition: border-color 0.13s, background 0.13s;
          margin-bottom: 6px;
          display: block;
        }
        .cp-course-btn:hover { border-color: #c4b5fd; background: #faf5ff; }
        .cp-course-btn.active { border-color: #7c3aed; background: #ede9fe; }

        /* ── Center: video + lesson list ── */
        .cp-center { display: flex; flex-direction: column; gap: 14px; min-width: 0; }

        /* video */
        .cp-video-wrap {
          background: #0f172a;
          border-radius: 14px;
          overflow: hidden;
          aspect-ratio: 16/9;
          display: flex;
          align-items: center;
          justify-content: center;
          box-shadow: 0 4px 20px rgba(0,0,0,0.12);
        }
        .cp-video-wrap video { width: 100%; height: 100%; object-fit: contain; display: block; }
        .cp-no-video {
          aspect-ratio: 16/9;
          background: linear-gradient(135deg, #1e1b4b, #2d1b69);
          border-radius: 14px;
          display: flex; flex-direction: column; align-items: center; justify-content: center;
          gap: 10px; color: #c4b5fd;
          box-shadow: 0 4px 20px rgba(0,0,0,0.12);
        }

        /* lesson list */
        .cp-lesson-list-body {
          max-height: 280px;
          overflow-y: auto;
          padding: 6px;
          scrollbar-width: thin;
          scrollbar-color: #cbd5e1 transparent;
        }
        .cp-lesson-list-body::-webkit-scrollbar { width: 4px; }
        .cp-lesson-list-body::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 99px; }
        .cp-lesson-btn {
          display: flex; align-items: center; gap: 10px;
          width: 100%; text-align: left;
          background: none;
          border: 1px solid transparent;
          border-radius: 9px;
          padding: 8px 10px;
          cursor: pointer;
          transition: background 0.12s, border-color 0.12s;
          margin-bottom: 2px;
        }
        .cp-lesson-btn:hover { background: #f8fafc; border-color: #e2e8f0; }
        .cp-lesson-btn.active { background: #ede9fe; border-color: #c4b5fd; }
        .cp-lesson-num {
          width: 24px; height: 24px; border-radius: 7px;
          background: #f1f5f9; color: #64748b;
          font-size: 0.7rem; font-weight: 700;
          display: flex; align-items: center; justify-content: center;
          flex-shrink: 0;
        }
        .cp-lesson-num.done { background: #d1fae5; color: #065f46; }
        .cp-lesson-num.cur { background: #7c3aed; color: white; }

        /* ── Right: AI rail ── */
        .cp-ai-rail {
          position: sticky;
          top: 16px;
          max-height: calc(100vh - 88px);
          display: flex;
          flex-direction: column;
          overflow: hidden;
        }
        .cp-ai-tabs {
          display: flex;
          border-bottom: 1px solid #e2e8f0;
          flex-shrink: 0;
        }
        .cp-ai-tab-btn {
          flex: 1;
          display: flex; align-items: center; justify-content: center; gap: 5px;
          padding: 11px 6px;
          border: none; background: none; cursor: pointer;
          font-size: 0.75rem; font-weight: 600;
          color: #94a3b8;
          transition: color 0.13s, background 0.13s;
          border-bottom: 2px solid transparent;
          position: relative; bottom: -1px;
        }
        .cp-ai-tab-btn:hover { background: #f8fafc; color: #475569; }
        .cp-ai-tab-btn.active-chat { color: #7c3aed; border-bottom-color: #7c3aed; }
        .cp-ai-tab-btn.active-quiz { color: #2563eb; border-bottom-color: #2563eb; }
        .cp-ai-tab-btn.active-summary { color: #d97706; border-bottom-color: #d97706; }
        .cp-ai-body {
          flex: 1;
          min-height: 0;
          display: flex;
          flex-direction: column;
          overflow: hidden;
          padding: 12px;
        }

        /* ── Misc ── */
        .cp-tag {
          display: inline-flex; align-items: center;
          padding: 2px 9px; border-radius: 100px;
          font-size: 0.67rem; font-weight: 600;
        }
        .cp-alert-success {
          padding: 9px 13px; background: #d1fae5; border: 1px solid #a7f3d0;
          border-radius: 10px; font-size: 0.8rem; color: #065f46; font-weight: 500;
          display: flex; align-items: center; gap: 7px;
          animation: slideIn 0.18s ease;
        }
        .cp-alert-error {
          padding: 9px 13px; background: #fee2e2; border: 1px solid #fecaca;
          border-radius: 10px; font-size: 0.8rem; color: #991b1b;
        }
        @keyframes slideIn { from { opacity:0; transform:translateY(-5px) } to { opacity:1; transform:translateY(0) } }
        .cp-stat-grid {
          display: grid; grid-template-columns: repeat(3,1fr); gap: 8px;
          padding: 0 16px 14px;
        }
        @media (max-width: 640px) { .cp-stat-grid { grid-template-columns: repeat(2,1fr); } }
        .cp-stat {
          background: #f8fafc; border: 1px solid #e2e8f0;
          border-radius: 10px; padding: 10px 12px;
        }
        .cp-spin {
          display: inline-block; width: 22px; height: 22px;
          border: 3px solid #e2e8f0; border-top-color: #7c3aed;
          border-radius: 50%; animation: spin 0.7s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg) } }
        .cp-empty {
          display: flex; flex-direction: column; align-items: center;
          padding: 60px 20px; text-align: center; color: #94a3b8;
        }
        .cp-empty-icon {
          width: 52px; height: 52px; border-radius: 14px; background: #f1f5f9;
          display: flex; align-items: center; justify-content: center; margin-bottom: 14px;
        }
        .cp-search-wrap { position: relative; }
        .cp-search-wrap input {
          padding-left: 32px; width: 100%; height: 34px;
          border: 1px solid #e2e8f0; border-radius: 9px;
          font-size: 0.78rem; color: #0f172a; background: #f8fafc;
          outline: none; transition: border-color 0.13s; font-family: inherit;
        }
        .cp-search-wrap input:focus { border-color: #a78bfa; background: white; }
        .cp-search-icon {
          position: absolute; left: 9px; top: 50%; transform: translateY(-50%);
          color: #94a3b8; pointer-events: none;
        }
      `}</style>

      <div className="cp">
        {/* Page title */}
        <div style={{ marginBottom: 16 }}>
          <h1 style={{ fontSize: "1.3rem", fontWeight: 700, color: "#0f172a", margin: 0 }}>
            {mode === "student" ? "My Courses" : "Child Courses"}
          </h1>
          <p style={{ fontSize: "0.85rem", color: "#64748b", margin: "3px 0 0" }}>
            {mode === "student" ? "Watch lessons, take quizzes, and track your progress." : "View courses assigned to your children."}
          </p>
        </div>

        {error && <div className="cp-alert-error" style={{ marginBottom: 12 }}>{error}</div>}
        {success && <div className="cp-alert-success" style={{ marginBottom: 12 }}><CheckCircle2 size={14} /> {success}</div>}

        <div className="cp-grid">

          {/* ═══════════════ LEFT: COURSE LIST ═══════════════ */}
          <div className="cp-card cp-course-panel">
            <div className="cp-course-head">
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 9 }}>
                <p style={{ fontSize: "0.82rem", fontWeight: 700, color: "#0f172a", margin: 0 }}>
                  {loading ? "Loading…" : `${visibleCourses.length} Course${visibleCourses.length !== 1 ? "s" : ""}`}
                </p>
                <button
                  type="button"
                  onClick={loadCourses}
                  style={{ background: "none", border: "1px solid #e2e8f0", borderRadius: 8, padding: "4px 8px", cursor: "pointer", color: "#64748b", display: "flex", alignItems: "center" }}
                  title="Refresh"
                >
                  <RefreshCcw size={13} />
                </button>
              </div>
              <div className="cp-search-wrap">
                <Search size={13} className="cp-search-icon" />
                <input placeholder="Search courses…" value={search} onChange={(e) => setSearch(e.target.value)} />
              </div>
            </div>

            <div className="cp-course-list">
              {loading && (
                <div style={{ padding: "24px 0", textAlign: "center" }}>
                  <div className="cp-spin" />
                </div>
              )}
              {!loading && visibleCourses.length === 0 && (
                <p style={{ textAlign: "center", color: "#94a3b8", fontSize: "0.8rem", padding: "24px 12px" }}>No courses found.</p>
              )}
              {visibleCourses.map((course, idx) => {
                const prog = Number(course.progress || 0);
                const { text, bg } = progressColor(prog);
                const isActive = selected?.id === course.id && selected?.student_id === course.student_id;
                return (
                  <button
                    key={`${course.id}-${course.student_id || idx}`}
                    type="button"
                    onClick={() => loadLessons(course)}
                    className={`cp-course-btn${isActive ? " active" : ""}`}
                  >
                    <div style={{ display: "flex", alignItems: "flex-start", gap: 9, marginBottom: 7 }}>
                      <div style={{ width: 33, height: 33, borderRadius: 9, flexShrink: 0, background: isActive ? "#7c3aed" : "#f1f5f9", display: "flex", alignItems: "center", justifyContent: "center" }}>
                        <BookOpen size={15} color={isActive ? "white" : "#7c3aed"} />
                      </div>
                      <div style={{ minWidth: 0, flex: 1 }}>
                        <p style={{ fontSize: "0.8rem", fontWeight: 700, color: isActive ? "#4c1d95" : "#0f172a", margin: 0, lineHeight: 1.35, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {course.title}
                        </p>
                        <p style={{ fontSize: "0.67rem", color: "#64748b", margin: "1px 0 0", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {[course.class_name, course.section_name, course.subject_name].filter(Boolean).join(" · ")}
                        </p>
                      </div>
                      <span className="cp-tag" style={{ background: bg, color: text, flexShrink: 0 }}>{Math.round(prog)}%</span>
                    </div>
                    <ProgressBar value={prog} h={3} />
                    <div style={{ display: "flex", gap: 10, marginTop: 5 }}>
                      <span style={{ fontSize: "0.67rem", color: "#94a3b8", display: "flex", alignItems: "center", gap: 3 }}>
                        <Layers size={10} /> {course.lessons_count || 0}
                      </span>
                      {course.teacher_name && (
                        <span style={{ fontSize: "0.67rem", color: "#94a3b8", display: "flex", alignItems: "center", gap: 3 }}>
                          <User size={10} /> {course.teacher_name}
                        </span>
                      )}
                      {mode === "parent" && course.student_name && (
                        <span style={{ fontSize: "0.67rem", color: "#94a3b8" }}>👤 {course.student_name}</span>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* ═══════════════ CENTER: VIDEO + LESSON LIST ═══════════════ */}
          <div className="cp-center">
            {!selected ? (
              <div className="cp-card cp-empty">
                <div className="cp-empty-icon"><BookOpen size={22} color="#7c3aed" /></div>
                <p style={{ fontSize: "0.9rem", fontWeight: 600, color: "#0f172a", margin: "0 0 5px" }}>Select a course to begin</p>
                <p style={{ fontSize: "0.82rem", color: "#94a3b8", margin: 0 }}>Choose a course from the left panel.</p>
              </div>
            ) : (
              <>
                {/* Video player */}
                {activeLesson ? (
                  activeLesson.video_url ? (
                    <OptimizedVideoPlayer
                      lesson={activeLesson}
                      mode={mode}
                      initialStatus={activeLessonProgress}
                      onStatusSynced={updateLessonWatchStatus}
                      onRegisterFlush={registerLessonFlusher}
                    />
                  ) : activeLesson.external_video_link ? (
                    <div className="cp-no-video">
                      <PlayCircle size={36} style={{ opacity: 0.6 }} />
                      <p style={{ margin: 0, fontWeight: 600, fontSize: "0.9rem" }}>{activeLesson.title}</p>
                      <a href={activeLesson.external_video_link} target="_blank" rel="noopener noreferrer"
                        style={{ padding: "7px 16px", borderRadius: 9, background: "rgba(124,58,237,0.3)", color: "#c4b5fd", textDecoration: "none", fontSize: "0.8rem", fontWeight: 600, display: "flex", alignItems: "center", gap: 6 }}>
                        <PlayCircle size={14} /> Open External Video
                      </a>
                    </div>
                  ) : (
                    <div className="cp-no-video">
                      <BookOpen size={36} style={{ opacity: 0.4 }} />
                      <p style={{ margin: 0, color: "#7c6aad", fontSize: "0.85rem" }}>No video for this lesson</p>
                    </div>
                  )
                ) : (
                  <div className="cp-no-video">
                    <PlayCircle size={36} style={{ opacity: 0.3 }} />
                    <p style={{ margin: 0, color: "#4a3f7a", fontSize: "0.85rem" }}>Select a lesson to watch</p>
                  </div>
                )}

                {/* Lesson info strip */}
                {activeLesson && (
                  <div className="cp-card">
                    <div style={{ padding: "13px 16px 10px", borderBottom: "1px solid #e2e8f0" }}>
                      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
                        <div style={{ minWidth: 0 }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 7, flexWrap: "wrap", marginBottom: 2 }}>
                            <span style={{ fontSize: "0.7rem", fontWeight: 700, color: "#94a3b8" }}>Lesson {activeLesson.order}</span>
                            {completedMap[activeLesson.id] && (
                              <span className="cp-tag" style={{ background: "#d1fae5", color: "#065f46" }}>
                                <CheckCircle2 size={10} style={{ marginRight: 3 }} /> Done
                              </span>
                            )}
                          </div>
                          <h3 style={{ fontSize: "0.95rem", fontWeight: 700, color: "#0f172a", margin: "0 0 2px" }}>{activeLesson.title}</h3>
                          {activeLesson.description && (
                            <p style={{ fontSize: "0.78rem", color: "#64748b", margin: 0 }}>{activeLesson.description}</p>
                          )}
                        </div>
                        <div style={{ display: "flex", gap: 6, flexShrink: 0, flexWrap: "wrap", alignItems: "center" }}>
                          {activeLesson.pdf_url && (
                            <a href={fileUrl(activeLesson.pdf_url)} target="_blank" rel="noopener noreferrer"
                              style={{ display: "inline-flex", alignItems: "center", gap: 5, padding: "6px 12px", borderRadius: 8, background: "#eff6ff", color: "#2563eb", textDecoration: "none", fontSize: "0.78rem", fontWeight: 600, border: "1px solid #bfdbfe" }}>
                              <FileText size={13} /> PDF Notes
                            </a>
                          )}
                          {mode === "student" && !completedMap[activeLesson.id] && (
                            <button type="button" onClick={() => markComplete(activeLesson)}
                              style={{ display: "inline-flex", alignItems: "center", gap: 5, padding: "6px 12px", borderRadius: 8, background: "#7c3aed", color: "white", border: "none", cursor: "pointer", fontSize: "0.78rem", fontWeight: 600 }}>
                              <CheckCircle2 size={13} /> Mark Complete
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                    {/* Course progress bar */}
                    <div className="cp-stat-grid">
                      <div className="cp-stat">
                        <p style={{ fontSize: "0.65rem", fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.05em", margin: "0 0 5px" }}>Progress</p>
                        <span style={{ fontSize: "1.1rem", fontWeight: 700, color: "#0f172a" }}>{overallProgress}%</span>
                        <ProgressBar value={overallProgress} h={3} />
                      </div>
                      <div className="cp-stat">
                        <p style={{ fontSize: "0.65rem", fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.05em", margin: "0 0 5px" }}>Lessons</p>
                        <span style={{ fontSize: "1.1rem", fontWeight: 700, color: "#0f172a" }}>{completedCount}</span>
                        <span style={{ fontSize: "0.78rem", color: "#94a3b8" }}> / {lessons.length}</span>
                      </div>
                      <div className="cp-stat">
                        <p style={{ fontSize: "0.65rem", fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.05em", margin: "0 0 5px" }}>Status</p>
                        <span style={{ fontSize: "0.78rem", fontWeight: 600, color: overallProgress >= 100 ? "#065f46" : overallProgress > 0 ? "#b45309" : "#64748b" }}>
                          {overallProgress >= 100 ? "✅ Completed" : overallProgress > 0 ? "🔥 In Progress" : "📚 Not Started"}
                        </span>
                      </div>
                    </div>
                  </div>
                )}

                {/* Lesson list */}
                <div className="cp-card">
                  <div style={{ padding: "12px 14px 10px", borderBottom: "1px solid #e2e8f0", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                      <Layers size={14} color="#7c3aed" />
                      <span style={{ fontSize: "0.85rem", fontWeight: 700, color: "#0f172a" }}>Lessons</span>
                      <span className="cp-tag" style={{ background: "#f1f5f9", color: "#64748b" }}>{lessons.length}</span>
                    </div>
                    {mode === "student" && (
                      <span style={{ fontSize: "0.72rem", color: "#94a3b8" }}>{completedCount}/{lessons.length} done</span>
                    )}
                  </div>
                  <div className="cp-lesson-list-body">
                    {lessons.length === 0 && (
                      <p style={{ textAlign: "center", color: "#94a3b8", fontSize: "0.8rem", padding: 20 }}>No lessons yet.</p>
                    )}
                    {lessons.map((lesson) => {
                      const done = completedMap[lesson.id];
                      const cur = activeLesson?.id === lesson.id;
                      return (
                        <button key={lesson.id} type="button" onClick={() => selectLesson(lesson)} className={`cp-lesson-btn${cur ? " active" : ""}`}>
                          <span className={`cp-lesson-num${done ? " done" : cur ? " cur" : ""}`}>
                            {done ? "✓" : lesson.order}
                          </span>
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <p style={{ fontSize: "0.8rem", fontWeight: cur ? 700 : 500, color: cur ? "#4c1d95" : "#0f172a", margin: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                              {lesson.title}
                            </p>
                            {lesson.description && (
                              <p style={{ fontSize: "0.68rem", color: "#94a3b8", margin: "1px 0 0", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                {lesson.description}
                              </p>
                            )}
                          </div>
                          <div style={{ display: "flex", gap: 5, flexShrink: 0, alignItems: "center" }}>
                            {lesson.video_url && <PlayCircle size={12} color="#94a3b8" />}
                            {lesson.pdf_url && <FileText size={12} color="#94a3b8" />}
                            {cur && <ChevronRight size={12} color="#7c3aed" />}
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>
              </>
            )}
          </div>

          {/* ═══════════════ RIGHT: AI TOOLS RAIL ═══════════════ */}
          <div className="cp-card cp-ai-rail">
            {/* Tab bar */}
            <div className="cp-ai-tabs">
              {aiTabs.map((tab) => {
                const Icon = tab.icon;
                const isActive = aiTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => setAiTab(tab.id)}
                    className={`cp-ai-tab-btn${isActive ? ` active-${tab.id}` : ""}`}
                  >
                    <Icon size={13} color={isActive ? tab.accent : undefined} />
                    {tab.label}
                  </button>
                );
              })}
            </div>

            {/* Tab body */}
            <div className="cp-ai-body">
              {!activeLesson ? (
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", flex: 1, gap: 10, color: "#94a3b8", padding: 24, textAlign: "center" }}>
                  <div style={{ width: 44, height: 44, borderRadius: 12, background: "#f1f5f9", display: "flex", alignItems: "center", justifyContent: "center" }}>
                    {aiTab === "chat" && <MessageCircle size={20} color="#7c3aed" />}
                    {aiTab === "quiz" && <ClipboardList size={20} color="#2563eb" />}
                    {aiTab === "summary" && <BookMarked size={20} color="#d97706" />}
                  </div>
                  <p style={{ fontSize: "0.82rem", fontWeight: 600, color: "#475569", margin: 0 }}>
                    {aiTab === "chat" ? "AI Chat" : aiTab === "quiz" ? "Quiz Generator" : "Summary"}
                  </p>
                  <p style={{ fontSize: "0.76rem", color: "#94a3b8", margin: 0 }}>Select a lesson to get started.</p>
                </div>
              ) : mode !== "student" ? (
                <div style={{ display: "flex", alignItems: "center", justifyContent: "center", flex: 1, color: "#94a3b8", fontSize: "0.8rem", padding: 24, textAlign: "center" }}>
                  AI tools are available for students only.
                </div>
              ) : (
                <>
                  {aiTab === "chat" && (
                    <CourseLessonChat
                      key={`chat-${activeLesson.id}-${aiKey}`}
                      lesson={activeLesson}
                      courseTitle={selected?.title}
                      embedded
                    />
                  )}
                  {aiTab === "quiz" && (
                    <LessonQuizGenerator
                      key={`quiz-${activeLesson.id}-${aiKey}`}
                      lesson={activeLesson}
                      courseTitle={selected?.title}
                      embedded
                    />
                  )}
                  {aiTab === "summary" && (
                    <LessonSummaryGenerator
                      key={`summary-${activeLesson.id}-${aiKey}`}
                      lesson={activeLesson}
                      courseTitle={selected?.title}
                      embedded
                    />
                  )}
                </>
              )}
            </div>
          </div>

        </div>
      </div>
    </>
  );
}

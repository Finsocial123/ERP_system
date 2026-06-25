"use client";

import AppShell from "@/components/AppShell";
import { useState, useEffect, useCallback } from "react";
import { getSavedAuth, apiFetch } from "@/lib/api";

type MeetingType = "teacher_class" | "admin_teachers";
type MeetingStatus = "scheduled" | "live" | "ended";

interface ClassOption {
  class_id: number;
  section_id: number | null;
  class_name: string;
  section_name: string | null;
}

interface MeetingOut {
  id: number;
  title: string;
  meeting_type: MeetingType;
  status: MeetingStatus;
  class_id: number | null;
  section_id: number | null;
  teacher_id: number | null;
  created_by_user_id: number;
  created_at: string;
  started_at: string | null;
  ended_at: string | null;
  scheduled_at: string | null;
  record: boolean;
  recording_url: string | null;
  class_name?: string;
  section_name?: string;
  teacher_name?: string;
}

interface MeetingListOut {
  items: MeetingOut[];
  total: number;
}

interface JoinResponse {
  join_url: string;
}
interface CreateMeetingResponse {
  meeting_id: number;
  join_url: string;
}

const STATUS_META: Record<
  MeetingStatus,
  { label: string; color: string; dot: string }
> = {
  scheduled: {
    label: "Scheduled",
    color: "bg-blue-50 text-blue-700",
    dot: "bg-blue-400",
  },
  live: {
    label: "Live",
    color: "bg-emerald-50 text-emerald-700",
    dot: "bg-emerald-500",
  },
  ended: {
    label: "Ended",
    color: "bg-slate-100 text-slate-500",
    dot: "bg-slate-400",
  },
};

const TYPE_META: Record<MeetingType, { label: string }> = {
  teacher_class: { label: "Class Meeting" },
  admin_teachers: { label: "Staff Meeting" },
};

function fmt(dt: string | null) {
  if (!dt) return "—";
  return new Date(dt).toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function fmtTime(dt: string | null) {
  if (!dt) return "—";
  return new Date(dt).toLocaleString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function duration(start: string | null, end: string | null): string {
  if (!start || !end) return "—";
  const ms = new Date(end).getTime() - new Date(start).getTime();
  const mins = Math.floor(ms / 60000);
  if (mins < 60) return `${mins}m`;
  return `${Math.floor(mins / 60)}h ${mins % 60}m`;
}

function deduplicateClasses(raw: ClassOption[]): ClassOption[] {
  const seen = new Set<string>();
  return raw.filter((cls) => {
    const key = `${cls.class_id}-${cls.section_name || cls.section_id || "null"}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
        onClick={onClose}
      />
      <div className="relative w-full max-w-lg bg-white rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
          <h2 className="text-lg font-semibold text-slate-800">{title}</h2>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-slate-100 text-slate-500 hover:text-slate-700 transition-colors"
          ></button>
        </div>
        <div className="overflow-y-auto flex-1 px-6 py-5">{children}</div>
      </div>
    </div>
  );
}

function RecordingSection({
  meetingId,
  existingUrl,
}: {
  meetingId: number;
  existingUrl: string | null;
}) {
  const [url, setUrl] = useState<string | null>(existingUrl);
  const [loading, setLoading] = useState(false);
  const [polled, setPolled] = useState(false);

  async function poll() {
    setLoading(true);
    try {
      const data = await apiFetch<{
        ready: boolean;
        recording_url: string | null;
      }>(`/meetings/${meetingId}/recording/fetch`, { method: "POST" });
      if (data.ready && data.recording_url) setUrl(data.recording_url);
    } catch {
      /* fail silently */
    } finally {
      setLoading(false);
      setPolled(true);
    }
  }

  if (url) {
    return (
      <div className="bg-violet-50 border border-violet-200 rounded-xl p-4 space-y-3">
        <div className="flex items-center gap-2">
          <div>
            <p className="text-sm font-semibold text-violet-900">
              Recording ready
            </p>
            <p className="text-xs text-violet-600">
              Watch the full session anytime
            </p>
          </div>
        </div>
        <button
          onClick={() => window.open(url, "_blank")}
          className="w-full py-2.5 bg-violet-600 text-white rounded-xl text-sm font-medium hover:bg-violet-700 transition-colors"
        >
          Watch Recording
        </button>
      </div>
    );
  }

  return (
    <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 space-y-3">
      <div className="flex items-center gap-2">
        <div>
          <p className="text-sm font-semibold text-slate-700">
            Recording processing
          </p>
          <p className="text-xs text-slate-500">
            BBB takes 5–30 mins after session ends
          </p>
        </div>
      </div>
      {polled && (
        <p className="text-xs text-amber-600 bg-amber-50 rounded-lg px-3 py-2">
          Not ready yet — check back in a few minutes
        </p>
      )}
      <button
        onClick={poll}
        disabled={loading}
        className="w-full py-2 text-sm border border-slate-200 rounded-xl hover:bg-white transition-colors disabled:opacity-50 font-medium text-slate-600"
      >
        {loading ? (
          <span className="flex items-center justify-center gap-2">
            <span className="w-3.5 h-3.5 border-2 border-slate-300 border-t-slate-600 rounded-full animate-spin" />
            Checking...
          </span>
        ) : (
          "Check for Recording"
        )}
      </button>
    </div>
  );
}

function TeacherMeetingForm({
  onClose,
  onCreated,
  onScheduled,
}: {
  onClose: () => void;
  onCreated: (joinUrl: string) => void;
  onScheduled: () => void;
}) {
  const [classes, setClasses] = useState<ClassOption[]>([]);
  const [classesLoading, setClassesLoading] = useState(true);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [mode, setMode] = useState<"now" | "schedule">("now");
  const [scheduledAt, setScheduledAt] = useState("");

  useEffect(() => {
    apiFetch<{ classes: ClassOption[] }>("/meetings/teacher/my-classes")
      .then(({ classes }) => setClasses(deduplicateClasses(classes)))
      .catch((e) => setError(e.message))
      .finally(() => setClassesLoading(false));
  }, []);

  const selectedClass =
    classes.find(
      (c) => `${c.class_id}-${c.section_name || c.section_id || "null"}` === selectedKey,
    ) ?? null;

  async function handleCreate() {
    if (!selectedClass || !title.trim()) return;
    if (mode === "schedule" && !scheduledAt) {
      setError("Please select a date and time");
      setLoading(false);
      return;
    }
    setError("");
    setLoading(true);
    try {
      if (mode === "now") {
        const data = await apiFetch<CreateMeetingResponse>(
          "/meetings/teacher/class",
          {
            method: "POST",
            body: JSON.stringify({
              class_id: selectedClass.class_id,
              section_id: selectedClass.section_id,
              section_name: selectedClass.section_name,
              title: title.trim(),
            }),
          },
        );
        onCreated(data.join_url);
      } else {
        await apiFetch("/meetings/teacher/class/schedule", {
          method: "POST",
          body: JSON.stringify({
            class_id: selectedClass.class_id,
            section_id: selectedClass.section_id,
            section_name: selectedClass.section_name,
            title: title.trim(),
            scheduled_at: new Date(scheduledAt).toISOString(),
          }),
        });
        onScheduled();
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  const inputCls =
    "w-full border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-300 bg-white";

  return (
    <div className="space-y-5">
      <div>
        <label className="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wider">
          Meeting Title
        </label>
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="e.g. Math Chapter 5 — Live Doubt Session"
          className={inputCls}
          autoFocus
        />
      </div>

      <div>
        <label className="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wider">
          Select Class
        </label>
        {classesLoading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-14 bg-slate-100 rounded-xl animate-pulse"
              />
            ))}
          </div>
        ) : classes.length === 0 ? (
          <p className="text-sm text-slate-400 py-3">
            No classes assigned to you yet.
          </p>
        ) : (
          <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
            {classes.map((cls) => {
              const key = `${cls.class_id}-${cls.section_name || cls.section_id || "null"}`;
              const isSelected = key === selectedKey;
              return (
                <button
                  key={key}
                  onClick={() => setSelectedKey(isSelected ? null : key)}
                  className={`w-full text-left px-4 py-3 rounded-xl border text-sm transition-all ${
                    isSelected
                      ? "border-slate-900 bg-slate-900 text-white"
                      : "border-slate-200 hover:border-slate-400 bg-white text-slate-700"
                  }`}
                >
                  <div className="font-medium">
                    {cls.class_name}
                    {cls.section_name && (
                      <span className="ml-1.5 px-1.5 py-0.5 rounded text-xs font-bold">
                        {cls.section_name}
                      </span>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {error && (
        <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">
          {error}
        </p>
      )}

      <div className="flex gap-2 p-1 bg-slate-100 rounded-xl">
        <button
          onClick={() => setMode("now")}
          className={`flex-1 py-2 text-sm rounded-lg font-medium transition-all ${
            mode === "now"
              ? "bg-white shadow-sm text-slate-900"
              : "text-slate-500"
          }`}
        >
          Start Now
        </button>
        <button
          onClick={() => setMode("schedule")}
          className={`flex-1 py-2 text-sm rounded-lg font-medium transition-all ${
            mode === "schedule"
              ? "bg-white shadow-sm text-slate-900"
              : "text-slate-500"
          }`}
        >
          Schedule
        </button>
      </div>

      {mode === "schedule" && (
        <div>
          <label className="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wider">
            Date & Time
          </label>
          <input
            type="datetime-local"
            value={scheduledAt}
            onChange={(e) => setScheduledAt(e.target.value)}
            min={new Date().toISOString().slice(0, 16)}
            className={inputCls}
          />
        </div>
      )}

      <div className="flex gap-3 pt-2 border-t border-slate-100">
        <button
          onClick={onClose}
          className="flex-1 py-2.5 text-sm border border-slate-200 rounded-xl hover:bg-slate-50 transition-colors text-slate-600"
        >
          Cancel
        </button>

        <button
          onClick={handleCreate}
          disabled={
            loading ||
            !title.trim() ||
            !selectedClass ||
            (mode === "schedule" && !scheduledAt)
          }
          className="flex-1 py-2.5 text-sm bg-emerald-600 text-white rounded-xl hover:bg-emerald-700 disabled:opacity-50 transition-colors font-medium"
        >
          {loading
            ? mode === "now"
              ? "Starting..."
              : "Scheduling..."
            : mode === "now"
              ? "Start Meeting"
              : "Schedule Meeting"}
        </button>
      </div>
    </div>
  );
}

function ScheduledMeetingCard({
  meeting,
  currentUserId,
  currentUserRole,
  onStart,
  onCancel,
}: {
  meeting: MeetingOut;
  currentUserId: number;
  currentUserRole: string;
  onStart: (id: number) => void;
  onCancel: (id: number) => void;
}) {
  const tm = TYPE_META[meeting.meeting_type];
  const isOwner =
    !!currentUserId && meeting.created_by_user_id === currentUserId;
  const canManage =
    isOwner ||
    ["SCHOOL_ADMIN", "SCHOOL_OWNER", "SUPER_ADMIN"].includes(currentUserRole);

  return (
    <div className="bg-white rounded-2xl border border-blue-200 p-5 space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-slate-800 truncate">
            {meeting.title}
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            {tm.label}
            {meeting.class_name
              ? ` · ${meeting.class_name}${meeting.section_name ?? ""}`
              : ""}
          </p>
        </div>
        <span className="flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full font-medium bg-blue-50 text-blue-700 shrink-0">
          <span className="w-1.5 h-1.5 rounded-full bg-blue-400" />
          Scheduled
        </span>
      </div>

      <div className="bg-slate-50 rounded-xl px-4 py-3 text-sm">
        <span className="text-slate-400 text-xs uppercase tracking-wider font-semibold">
          Scheduled for
        </span>
        <p className="text-slate-800 font-medium mt-0.5">
          {fmtTime(meeting.scheduled_at)}
        </p>
      </div>

      {canManage && (
        <div className="flex gap-2">
          <button
            onClick={() => onStart(meeting.id)}
            className="flex-1 py-2 text-sm font-medium bg-emerald-600 text-white rounded-xl hover:bg-emerald-700 transition-colors"
          >
            Start Now
          </button>
          <button
            onClick={() => onCancel(meeting.id)}
            className="px-4 py-2 text-sm border border-red-200 text-red-600 rounded-xl hover:bg-red-50 transition-colors"
          >
            Cancel
          </button>
        </div>
      )}
    </div>
  );
}

function AdminMeetingForm({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (joinUrl: string) => void;
}) {
  const [title, setTitle] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleCreate() {
    if (!title.trim()) return;
    setError("");
    setLoading(true);
    try {
      const data = await apiFetch<CreateMeetingResponse>(
        "/meetings/admin/teachers",
        {
          method: "POST",
          body: JSON.stringify({ title: title.trim() }),
        },
      );
      onCreated(data.join_url);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  const inputCls =
    "w-full border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-300 bg-white";

  return (
    <div className="space-y-5">
      <div>
        <label className="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wider">
          Meeting Title
        </label>
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="e.g. Weekly Staff Briefing"
          className={inputCls}
          autoFocus
        />
      </div>
      <div className="bg-blue-50 border border-blue-200 rounded-xl px-4 py-3 text-xs text-blue-700 space-y-1">
        <p className="font-semibold">Staff meeting:</p>
        <p>- All teachers in the school can join as attendees</p>
        <p>- You join as moderator with full controls</p>
        <p>- Session is recorded automatically</p>
      </div>
      {error && (
        <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">
          {error}
        </p>
      )}
      <div className="flex gap-3 pt-2 border-t border-slate-100">
        <button
          onClick={onClose}
          className="flex-1 py-2.5 text-sm border border-slate-200 rounded-xl hover:bg-slate-50 transition-colors text-slate-600"
        >
          Cancel
        </button>
        <button
          onClick={handleCreate}
          disabled={loading || !title.trim()}
          className="flex-1 py-2.5 text-sm bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-50 transition-colors font-medium"
        >
          {loading ? "Starting..." : " Start Staff Meeting"}
        </button>
      </div>
    </div>
  );
}

function MeetingCard({
  meeting,
  currentUserId,
  currentUserRole,
  onJoin,
  onEnd,
  onView,
  joining,
  ending,
}: {
  meeting: MeetingOut;
  currentUserId: number;
  currentUserRole: string;
  onJoin: (id: number) => void;
  onEnd: (id: number) => void;
  onView: (m: MeetingOut) => void;
  joining: number | null;
  ending: number | null;
}) {
  const sm = STATUS_META[meeting.status];
  const tm = TYPE_META[meeting.meeting_type];
  const isLive = meeting.status === "live";
  const isEnded = meeting.status === "ended";
  const isOwner = meeting.created_by_user_id === currentUserId;
  // FIX: guard End button — only teachers/admins who own the meeting can end it
  const canEnd =
    isOwner &&
    ["TEACHER", "SCHOOL_ADMIN", "SCHOOL_OWNER", "SUPER_ADMIN"].includes(
      currentUserRole,
    );

  return (
    <div
      className={`group relative bg-white rounded-2xl border transition-all duration-200 hover:shadow-lg hover:-translate-y-0.5 ${isLive ? "border-emerald-300 shadow-emerald-100 shadow-md" : "border-slate-200"}`}
    >
      {isLive && (
        <div className="absolute -top-2.5 left-4 flex items-center gap-1.5 bg-emerald-500 text-white text-[10px] font-bold px-2.5 py-0.5 rounded-full shadow-sm">
          <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />
          LIVE NOW
        </div>
      )}
      <div className="p-5">
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <h3 className="font-semibold text-slate-800 truncate">
                {meeting.title}
              </h3>
            </div>
            <p className="text-xs text-slate-400">
              {tm.label}
              {meeting.class_name
                ? ` · ${meeting.class_name}${meeting.section_name ?? ""}`
                : ""}
            </p>
          </div>
          <span
            className={`flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full font-medium shrink-0 ${sm.color}`}
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${sm.dot} ${isLive ? "animate-pulse" : ""}`}
            />
            {sm.label}
          </span>
        </div>

        <div className="grid grid-cols-2 gap-2 mb-4 text-xs text-slate-500">
          <div>
            <span className="text-slate-400">Started</span>
            <p className="text-slate-700 font-medium">
              {fmtTime(meeting.started_at ?? meeting.created_at)}
            </p>
          </div>
          {isEnded && (
            <div>
              <span className="text-slate-400">Duration</span>
              <p className="text-slate-700 font-medium">
                {duration(meeting.started_at, meeting.ended_at)}
              </p>
            </div>
          )}
          {meeting.record && (
            <div className="col-span-2 flex items-center gap-1 text-slate-400">
              <span>Recorded</span>
              {isEnded && meeting.recording_url && (
                <span className="ml-1 text-violet-600 font-medium">
                  · Ready
                </span>
              )}
            </div>
          )}
        </div>

        <div className="flex gap-2">
          {isLive && (
            <button
              onClick={() => onJoin(meeting.id)}
              disabled={joining === meeting.id}
              className="flex-1 py-2 text-sm font-medium bg-emerald-600 text-white rounded-xl hover:bg-emerald-700 disabled:opacity-60 transition-colors"
            >
              {joining === meeting.id ? "Opening..." : "Join Meeting"}
            </button>
          )}
          {/* FIX: use canEnd instead of isOwner alone */}
          {isLive && canEnd && (
            <button
              onClick={() => onEnd(meeting.id)}
              disabled={ending === meeting.id}
              className="px-4 py-2 text-sm font-medium border border-red-200 text-red-600 rounded-xl hover:bg-red-50 disabled:opacity-60 transition-colors"
            >
              {ending === meeting.id ? "Ending..." : "End"}
            </button>
          )}
          {isEnded && (
            <button
              onClick={() => onView(meeting)}
              className="flex-1 py-2 text-sm border border-slate-200 text-slate-600 rounded-xl hover:bg-slate-50 transition-colors"
            >
              {meeting.recording_url ? " View & Watch" : "View Details"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function MeetingDetailModal({
  meeting,
  onClose,
}: {
  meeting: MeetingOut;
  onClose: () => void;
}) {
  const sm = STATUS_META[meeting.status];
  const tm = TYPE_META[meeting.meeting_type];

  return (
    <Modal title={meeting.title} onClose={onClose}>
      <div className="space-y-4">
        <div className="flex flex-wrap gap-2">
          <span
            className={`flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full font-medium ${sm.color}`}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${sm.dot}`} />
            {sm.label}
          </span>
          <span className="text-xs px-2.5 py-1 rounded-full bg-slate-100 text-slate-600 font-medium">
            {tm.label}
          </span>
          {meeting.record && (
            <span className="text-xs px-2.5 py-1 rounded-full bg-slate-100 text-slate-600 font-medium">
              {" "}
              Recorded
            </span>
          )}
        </div>

        <div className="grid grid-cols-2 gap-3 bg-slate-50 rounded-xl p-4 text-sm">
          <div>
            <span className="text-slate-400 text-xs uppercase tracking-wider font-semibold">
              Started
            </span>
            <p className="text-slate-800 font-medium mt-0.5">
              {fmtTime(meeting.started_at ?? meeting.created_at)}
            </p>
          </div>
          <div>
            <span className="text-slate-400 text-xs uppercase tracking-wider font-semibold">
              Ended
            </span>
            <p className="text-slate-800 font-medium mt-0.5">
              {fmtTime(meeting.ended_at)}
            </p>
          </div>
          <div>
            <span className="text-slate-400 text-xs uppercase tracking-wider font-semibold">
              Duration
            </span>
            <p className="text-slate-800 font-medium mt-0.5">
              {duration(meeting.started_at, meeting.ended_at)}
            </p>
          </div>
          {meeting.class_name && (
            <div>
              <span className="text-slate-400 text-xs uppercase tracking-wider font-semibold">
                Class
              </span>
              <p className="text-slate-800 font-medium mt-0.5">
                {meeting.class_name}
                {meeting.section_name ?? ""}
              </p>
            </div>
          )}
        </div>

        {meeting.record && (
          <RecordingSection
            meetingId={meeting.id}
            existingUrl={meeting.recording_url}
          />
        )}
      </div>
    </Modal>
  );
}

function LaunchModal({
  joinUrl,
  onClose,
}: {
  joinUrl: string;
  onClose: () => void;
}) {
  const [copied, setCopied] = useState(false);
  function copy() {
    navigator.clipboard.writeText(joinUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }
  return (
    <Modal title="Meeting Ready" onClose={onClose}>
      <div className="space-y-5 text-center">
        <div>
          <p className="text-slate-800 font-semibold text-lg">
            Your meeting is live!
          </p>
          <p className="text-slate-500 text-sm mt-1">
            Click below to enter the classroom.
          </p>
        </div>
        <button
          onClick={() => {
            window.open(joinUrl, "_blank");
            onClose();
          }}
          className="w-full py-3 bg-emerald-600 text-white rounded-xl font-semibold hover:bg-emerald-700 transition-colors"
        >
          Enter Classroom
        </button>
        <div className="bg-slate-50 border border-slate-200 rounded-xl p-3 text-left space-y-2">
          <p className="text-xs text-slate-500 font-medium">Direct join link</p>
          <p className="text-xs text-slate-700 break-all font-mono">
            {joinUrl}
          </p>
          <button
            onClick={copy}
            className="text-xs px-3 py-1 border border-slate-200 rounded-lg hover:bg-white transition-colors text-slate-600"
          >
            {copied ? " Copied!" : "Copy link"}
          </button>
        </div>
        <button
          onClick={onClose}
          className="w-full py-2 text-sm text-slate-400 hover:text-slate-600 transition-colors"
        >
          Dismiss
        </button>
      </div>
    </Modal>
  );
}

type Tab = "live" | "scheduled" | "past";

export default function MeetingsPage() {
  const auth = getSavedAuth();
  const currentUserId: number = auth?.user?.id ?? 0;
  const currentUserRole: string = auth?.user?.role ?? "";
  const isAdmin = ["SUPER_ADMIN", "SCHOOL_OWNER", "SCHOOL_ADMIN"].includes(
    currentUserRole,
  );
  const isTeacher = currentUserRole === "TEACHER";
  const canCreate = isAdmin || isTeacher;

  const [activeTab, setActiveTab] = useState<Tab>("live");
  const [liveMeetings, setLiveMeetings] = useState<MeetingListOut | null>(null);
  const [pastMeetings, setPastMeetings] = useState<MeetingListOut | null>(null);
  const [liveLoading, setLiveLoading] = useState(true);
  const [pastLoading, setPastLoading] = useState(false);
  const [liveError, setLiveError] = useState("");
  const [pastError, setPastError] = useState("");
  const [pastSkip, setPastSkip] = useState(0);
  // FIX: version counter to force past tab refresh after ending a meeting
  const [pastVersion, setPastVersion] = useState(0);
  const limit = 12;

  const [creatingTeacher, setCreatingTeacher] = useState(false);
  const [creatingAdmin, setCreatingAdmin] = useState(false);
  const [launchUrl, setLaunchUrl] = useState<string | null>(null);
  const [viewingMeeting, setViewingMeeting] = useState<MeetingOut | null>(null);
  const [endingId, setEndingId] = useState<number | null>(null);
  const [joining, setJoining] = useState<number | null>(null);
  const [ending, setEnding] = useState<number | null>(null);

  const [scheduledMeetings, setScheduledMeetings] =
    useState<MeetingListOut | null>(null);
  const [scheduledLoading, setScheduledLoading] = useState(false);
  const [scheduledError, setScheduledError] = useState("");
  const [scheduledVersion, setScheduledVersion] = useState(0);

  const fetchScheduled = useCallback(async () => {
    setScheduledLoading(true);
    setScheduledError("");
    try {
      const data = await apiFetch<MeetingListOut>(
        "/meetings/?status=scheduled&limit=50",
      );
      setScheduledMeetings(data);
    } catch (e: any) {
      setScheduledError(e.message);
    } finally {
      setScheduledLoading(false);
    }
  }, []);

  useEffect(() => {
    if (activeTab === "scheduled") fetchScheduled();
  }, [activeTab, fetchScheduled, scheduledVersion]);

  const fetchLive = useCallback(async () => {
    setLiveLoading(true);
    setLiveError("");
    try {
      const data = await apiFetch<MeetingListOut>(
        "/meetings/?status=live&limit=50",
      );
      setLiveMeetings(data);
    } catch (e: any) {
      setLiveError(e.message);
    } finally {
      setLiveLoading(false);
    }
  }, []);

  const fetchPast = useCallback(async () => {
    setPastLoading(true);
    setPastError("");
    try {
      const params = new URLSearchParams({
        status: "ended",
        skip: String(pastSkip),
        limit: String(limit),
      });
      const data = await apiFetch<MeetingListOut>(`/meetings/?${params}`);
      setPastMeetings(data);
    } catch (e: any) {
      setPastError(e.message);
    } finally {
      setPastLoading(false);
    }
  }, [pastSkip]);

  useEffect(() => {
    fetchLive();
  }, [fetchLive]);

  // FIX: pastVersion added so switching to past tab after ending a meeting always refreshes
  useEffect(() => {
    if (activeTab === "past") fetchPast();
  }, [activeTab, fetchPast, pastVersion]);

  useEffect(() => {
    if (activeTab !== "live") return;
    const interval = setInterval(fetchLive, 60000);
    return () => clearInterval(interval);
  }, [activeTab, fetchLive]);

  async function handleStart(meetingId: number) {
    try {
      const data = await apiFetch<CreateMeetingResponse>(
        `/meetings/${meetingId}/start`,
        { method: "POST" },
      );
      setScheduledVersion((v) => v + 1);
      fetchLive();
      setLaunchUrl(data.join_url);
    } catch (e: any) {
      alert(e.message);
    }
  }

  async function handleCancel(meetingId: number) {
    try {
      await apiFetch(`/meetings/${meetingId}/cancel`, { method: "DELETE" });
      setScheduledVersion((v) => v + 1);
    } catch (e: any) {
      alert(e.message);
    }
  }

  async function handleJoin(meetingId: number) {
    setJoining(meetingId);
    try {
      const data = await apiFetch<JoinResponse>(`/meetings/${meetingId}/join`);
      window.open(data.join_url, "_blank");
    } catch (e: any) {
      alert(e.message);
    } finally {
      setJoining(null);
    }
  }

  async function handleEnd(meetingId: number) {
    setEnding(meetingId);
    try {
      await apiFetch(`/meetings/${meetingId}/end`, { method: "POST" });
      fetchLive();
      // FIX: bump pastVersion so past tab refreshes when user switches to it
      setPastVersion((v) => v + 1);
    } catch (e: any) {
      alert(e.message);
    } finally {
      // FIX: always close modal in finally, even on error
      setEnding(null);
      setEndingId(null);
    }
  }

  function handleCreated(joinUrl: string) {
    setCreatingTeacher(false);
    setCreatingAdmin(false);
    setLaunchUrl(joinUrl);
    fetchLive();
  }

  const pastPages = pastMeetings ? Math.ceil(pastMeetings.total / limit) : 0;
  const pastPage = Math.floor(pastSkip / limit) + 1;
  const liveCount = liveMeetings?.items.length ?? 0;

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Meetings</h1>
            {liveCount > 0 && (
              <p className="text-sm text-slate-500 mt-0.5">
                <span className="font-semibold text-emerald-600">
                  {liveCount} live
                </span>{" "}
                {liveCount === 1 ? "session" : "sessions"} happening now
              </p>
            )}
          </div>
          {canCreate && (
            <div className="flex items-center gap-2">
              {isTeacher && (
                <button
                  onClick={() => setCreatingTeacher(true)}
                  className="flex items-center gap-2 px-4 py-2.5 bg-emerald-600 text-white text-sm font-medium rounded-xl hover:bg-emerald-700 transition-colors"
                >
                  Start Class Meeting
                </button>
              )}
              {isAdmin && (
                <button
                  onClick={() => setCreatingAdmin(true)}
                  className="flex items-center gap-2 px-4 py-2.5 bg-slate-900 text-white text-sm font-medium rounded-xl hover:bg-slate-700 transition-colors"
                >
                  Staff Meeting
                </button>
              )}
            </div>
          )}
        </div>

        {/* Tabs */}
        <div className="flex gap-1 bg-slate-100 rounded-xl p-1 w-fit">
          {(
            [
              ["live", "Live & Upcoming"],
              ["scheduled", "Scheduled"],
              ["past", "Past Meetings"],
            ] as [Tab, string][]
          ).map(([tab, label]) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-5 py-2 text-sm font-medium rounded-lg transition-all ${activeTab === tab ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"}`}
            >
              {label}
              {tab === "live" && liveCount > 0 && (
                <span className="ml-2 bg-emerald-500 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full">
                  {liveCount}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Live Tab */}
        {activeTab === "live" && (
          <div className="space-y-4">
            {liveLoading && (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                {Array.from({ length: 3 }).map((_, i) => (
                  <div
                    key={i}
                    className="h-52 bg-white rounded-2xl border border-slate-200 animate-pulse"
                  />
                ))}
              </div>
            )}
            {liveError && (
              <div className="text-center py-20">
                <p className="text-red-600 text-sm font-medium mb-3">
                  {liveError}
                </p>
                <button
                  onClick={fetchLive}
                  className="text-sm text-blue-600 underline"
                >
                  Try again
                </button>
              </div>
            )}
            {!liveLoading &&
              !liveError &&
              liveMeetings &&
              (liveMeetings.items.length === 0 ? (
                <div className="text-center py-24">
                  <div className="text-5xl mb-4"></div>
                  <p className="text-slate-600 text-lg font-medium mb-2">
                    No live sessions right now
                  </p>
                  <p className="text-slate-400 text-sm mb-6">
                    {canCreate
                      ? "Start a meeting to begin a live session"
                      : "Check back when a teacher starts a class"}
                  </p>
                  {isTeacher && (
                    <button
                      onClick={() => setCreatingTeacher(true)}
                      className="px-5 py-2.5 bg-emerald-600 text-white text-sm font-medium rounded-xl hover:bg-emerald-700 transition-colors"
                    >
                      Start a Class Meeting
                    </button>
                  )}
                  {isAdmin && (
                    <button
                      onClick={() => setCreatingAdmin(true)}
                      className="ml-3 px-5 py-2.5 bg-slate-900 text-white text-sm font-medium rounded-xl hover:bg-slate-700 transition-colors"
                    >
                      Start Staff Meeting
                    </button>
                  )}
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                  {liveMeetings.items.map((m) => (
                    <MeetingCard
                      key={m.id}
                      meeting={m}
                      currentUserId={currentUserId}
                      currentUserRole={currentUserRole}
                      onJoin={handleJoin}
                      onEnd={(id) => setEndingId(id)}
                      onView={setViewingMeeting}
                      joining={joining}
                      ending={ending}
                    />
                  ))}
                </div>
              ))}
          </div>
        )}

        {activeTab === "scheduled" && (
          <div className="space-y-4">
            {scheduledLoading && (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                {Array.from({ length: 3 }).map((_, i) => (
                  <div
                    key={i}
                    className="h-44 bg-white rounded-2xl border border-slate-100 animate-pulse"
                  />
                ))}
              </div>
            )}
            {scheduledError && (
              <div className="text-center py-16">
                <p className="text-red-600 text-sm mb-3">{scheduledError}</p>
                <button
                  onClick={fetchScheduled}
                  className="text-sm text-slate-500 underline"
                >
                  Retry
                </button>
              </div>
            )}
            {!scheduledLoading &&
              !scheduledError &&
              scheduledMeetings &&
              (scheduledMeetings.items.length === 0 ? (
                <div className="text-center py-24">
                  <p className="text-slate-600 text-lg font-medium">
                    No scheduled meetings
                  </p>
                  <p className="text-slate-400 text-sm mt-1">
                    Schedule a meeting to see it here
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                  {scheduledMeetings.items.map((m) => (
                    <ScheduledMeetingCard
                      key={m.id}
                      meeting={m}
                      currentUserId={currentUserId}
                      currentUserRole={currentUserRole}
                      onStart={handleStart}
                      onCancel={handleCancel}
                    />
                  ))}
                </div>
              ))}
          </div>
        )}

        {/* Past Tab */}
        {activeTab === "past" && (
          <div className="space-y-4">
            {pastLoading && (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                {Array.from({ length: 6 }).map((_, i) => (
                  <div
                    key={i}
                    className="h-44 bg-white rounded-2xl border border-slate-100 animate-pulse"
                  />
                ))}
              </div>
            )}
            {pastError && (
              <div className="text-center py-16">
                <p className="text-red-600 text-sm mb-3">{pastError}</p>
                <button
                  onClick={fetchPast}
                  className="text-sm text-slate-500 underline"
                >
                  Retry
                </button>
              </div>
            )}
            {!pastLoading &&
              !pastError &&
              pastMeetings &&
              (pastMeetings.items.length === 0 ? (
                <div className="text-center py-24">
                  <div className="text-5xl mb-4">️</div>
                  <p className="text-slate-600 text-lg font-medium">
                    No past meetings yet
                  </p>
                  <p className="text-slate-400 text-sm mt-1">
                    Ended sessions will appear here
                  </p>
                </div>
              ) : (
                <>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                    {pastMeetings.items.map((m) => (
                      <MeetingCard
                        key={m.id}
                        meeting={m}
                        currentUserId={currentUserId}
                        currentUserRole={currentUserRole}
                        onJoin={handleJoin}
                        onEnd={(id) => setEndingId(id)}
                        onView={setViewingMeeting}
                        joining={joining}
                        ending={ending}
                      />
                    ))}
                  </div>
                  {pastPages > 1 && (
                    <div className="flex items-center justify-center gap-3 mt-6">
                      <button
                        onClick={() =>
                          setPastSkip((s) => Math.max(0, s - limit))
                        }
                        disabled={pastSkip === 0}
                        className="px-4 py-2 text-sm border border-slate-200 rounded-xl disabled:opacity-40 hover:bg-slate-50 transition-colors bg-white font-medium"
                      >
                        Previous
                      </button>
                      <span className="text-sm text-slate-600 font-medium">
                        Page {pastPage} of {pastPages}
                      </span>
                      <button
                        onClick={() => setPastSkip((s) => s + limit)}
                        disabled={
                          pastSkip + limit >= (pastMeetings?.total ?? 0)
                        }
                        className="px-4 py-2 text-sm border border-slate-200 rounded-xl disabled:opacity-40 hover:bg-slate-50 transition-colors bg-white font-medium"
                      >
                        Next
                      </button>
                    </div>
                  )}
                </>
              ))}
          </div>
        )}
      </div>

      {creatingTeacher && (
        <Modal
          title="Start Class Meeting"
          onClose={() => setCreatingTeacher(false)}
        >
          <TeacherMeetingForm
            onClose={() => setCreatingTeacher(false)}
            onCreated={handleCreated}
            onScheduled={() => {
              setCreatingTeacher(false);
              setScheduledVersion((v) => v + 1);
              setActiveTab("scheduled");
            }}
          />
        </Modal>
      )}
      {creatingAdmin && (
        <Modal
          title="Start Staff Meeting"
          onClose={() => setCreatingAdmin(false)}
        >
          <AdminMeetingForm
            onClose={() => setCreatingAdmin(false)}
            onCreated={handleCreated}
          />
        </Modal>
      )}
      {launchUrl && (
        <LaunchModal joinUrl={launchUrl} onClose={() => setLaunchUrl(null)} />
      )}
      {viewingMeeting && (
        <MeetingDetailModal
          meeting={viewingMeeting}
          onClose={() => setViewingMeeting(null)}
        />
      )}

      {endingId !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div
            className="absolute inset-0 bg-black/40 backdrop-blur-sm"
            onClick={() => setEndingId(null)}
          />
          <div className="relative bg-white rounded-2xl shadow-2xl p-6 w-full max-w-sm text-center space-y-4">
            <div className="text-4xl">️</div>
            <h3 className="font-semibold text-slate-800">End this meeting?</h3>
            <p className="text-sm text-slate-500">
              All participants will be removed and the session will be closed.
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setEndingId(null)}
                className="flex-1 py-2 text-sm border border-slate-200 rounded-xl hover:bg-slate-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => handleEnd(endingId)}
                disabled={ending === endingId}
                className="flex-1 py-2 text-sm bg-red-600 text-white rounded-xl hover:bg-red-700 disabled:opacity-60 transition-colors"
              >
                {ending === endingId ? "Ending..." : "End Meeting"}
              </button>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}

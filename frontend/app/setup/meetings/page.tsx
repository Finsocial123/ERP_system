"use client";

import AppShell from "@/components/AppShell";
import { useState, useEffect, useCallback, useRef } from "react";
import { getSavedAuth } from "@/lib/api";
import { apiFetch } from "@/lib/api";

type MeetingType = "teacher_class" | "admin_teachers";
type MeetingStatus = "scheduled" | "live" | "ended";

interface CreatedByOut {
  id: number;
  full_name: string;
  role: string;
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
  created_by: CreatedByOut | null;
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

interface StatsOut {
  total_meetings: number;
  live_now: number;
  total_ended: number;
  recorded: number;
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

const TYPE_META: Record<MeetingType, { label: string; color: string }> = {
  teacher_class: {
    label: "Class Meeting",
    color: "bg-violet-50 text-violet-700",
  },
  admin_teachers: {
    label: "Staff Meeting",
    color: "bg-blue-50 text-blue-700",
  },
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
          >
            ✕
          </button>
        </div>
        <div className="overflow-y-auto flex-1 px-6 py-5">{children}</div>
      </div>
    </div>
  );
}

function StatsRow({
  stats,
  loading,
}: {
  stats: StatsOut | null;
  loading: boolean;
}) {
  const cards = [
    {
      label: "Total Meetings",
      value: stats?.total_meetings ?? 0,
      color: "bg-slate-50 border-slate-200",
      text: "text-slate-700",
    },
    {
      label: "Live Now",
      value: stats?.live_now ?? 0,
      color: "bg-emerald-50 border-emerald-200",
      text: "text-emerald-700",
    },
    {
      label: "Completed",
      value: stats?.total_ended ?? 0,
      color: "bg-blue-50 border-blue-200",
      text: "text-blue-700",
    },
    {
      label: "Recorded",
      value: stats?.recorded ?? 0,
      color: "bg-violet-50 border-violet-200",
      text: "text-violet-700",
    },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map((c) => (
        <div key={c.label} className={`rounded-2xl border p-4 ${c.color}`}>
          {loading ? (
            <div className="space-y-2">
              <div className="h-7 w-16 bg-slate-200 rounded animate-pulse" />
              <div className="h-3 w-24 bg-slate-200 rounded animate-pulse" />
            </div>
          ) : (
            <>
              <span className={`text-2xl font-bold ${c.text}`}>{c.value}</span>
              <p className="text-xs text-slate-500 font-medium mt-1">
                {c.label}
              </p>
            </>
          )}
        </div>
      ))}
    </div>
  );
}

function StaffMeetingForm({
  onClose,
  onCreated,
  onScheduled,
}: {
  onClose: () => void;
  onCreated: (joinUrl: string) => void;
  onScheduled: () => void;
}) {
  const [title, setTitle] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [mode, setMode] = useState<"now" | "schedule">("now");
  const [scheduledAt, setScheduledAt] = useState("");

  async function handleCreate() {
    if (!title.trim()) return;

    if (mode === "schedule" && !scheduledAt) {
      setError("Please select a date and time");
      return;
    }

    setError("");
    setLoading(true);
    try {
      if (mode === "now") {
        const data = await apiFetch<CreateMeetingResponse>(
          "/meetings/admin/teachers",
          {
            method: "POST",
            body: JSON.stringify({ title: title.trim() }),
          },
        );
        onCreated(data.join_url);
      } else {
        await apiFetch("/meetings/admin/teachers/schedule", {
          method: "POST",
          body: JSON.stringify({
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
          placeholder="e.g. Weekly Staff Briefing, PTM Prep"
          className={inputCls}
          autoFocus
        />
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
            loading || !title.trim() || (mode === "schedule" && !scheduledAt)
          }
          className="flex-1 py-2.5 text-sm bg-slate-900 text-white rounded-xl hover:bg-slate-700 disabled:opacity-50 transition-colors font-medium"
        >
          {loading
            ? mode === "now"
              ? "Starting..."
              : "Scheduling..."
            : mode === "now"
              ? "Start Staff Meeting"
              : "Schedule Staff Meeting"}
        </button>
      </div>
    </div>
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
            Click below to enter the Meeting.
          </p>
        </div>
        <button
          onClick={() => {
            window.open(joinUrl, "_blank");
            onClose();
          }}
          className="w-full py-3 bg-emerald-600 text-white rounded-xl font-semibold hover:bg-emerald-700 transition-colors"
        >
          Enter Meeting
        </button>
        <div className="bg-slate-50 border border-slate-200 rounded-xl p-3 text-left space-y-2">
          <p className="text-xs text-slate-500 font-medium">Direct join link</p>
          <p className="text-xs text-slate-700 break-all font-mono leading-relaxed">
            {joinUrl}
          </p>
          <button
            onClick={copy}
            className="text-xs px-3 py-1 border border-slate-200 rounded-lg hover:bg-white transition-colors text-slate-600"
          >
            {copied ? "Copied!" : "Copy link"}
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

function MeetingRow({
  meeting,
  currentUserId,
  onJoin,
  onEnd,
  onView,
  joining,
  ending,
  onStart,
  onCancel,
  currentUserRole,
}: {
  meeting: MeetingOut;
  currentUserId: number;
  onJoin: (id: number) => void;
  onEnd: (id: number) => void;
  onStart: (id: number) => void;
  onCancel: (id: number) => void;
  onView: (m: MeetingOut) => void;
  joining: number | null;
  ending: number | null;
  currentUserRole: string;
}) {
  const sm = STATUS_META[meeting.status];
  const tm = TYPE_META[meeting.meeting_type];
  const isLive = meeting.status === "live";
  const isOwner = meeting.created_by_user_id === currentUserId;
  const canEnd =
    isOwner ||
    ["SCHOOL_ADMIN", "SCHOOL_OWNER", "SUPER_ADMIN"].includes(currentUserRole);

  const isScheduled = meeting.status === "scheduled";
  return (
    <div
      className={`group flex items-center gap-4 px-5 py-4 bg-white rounded-2xl border transition-all hover:shadow-sm ${
        isLive ? "border-emerald-200 bg-emerald-50/30" : "border-slate-100"
      }`}
    >
      {/* Type pill */}
      <div
        className={`px-2.5 py-1 rounded-lg text-xs font-medium shrink-0 ${tm.color}`}
      >
        {tm.label}
      </div>

      {/* Main info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          {isLive && (
            <span className="flex items-center gap-1 text-[10px] font-bold text-emerald-600 bg-emerald-100 px-2 py-0.5 rounded-full shrink-0">
              <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-pulse" />
              LIVE
            </span>
          )}
          <p className="font-semibold text-slate-800 truncate text-sm">
            {meeting.title}
          </p>
        </div>
        <div className="flex items-center gap-3 mt-0.5 text-xs text-slate-400">
          {meeting.class_name && (
            <span>
              {meeting.class_name}
              {meeting.section_name ? ` ${meeting.section_name}` : ""}
            </span>
          )}
          {meeting.teacher_name && <span>· {meeting.teacher_name}</span>}
          <span>· {fmt(meeting.created_at)}</span>
          {meeting.status === "ended" &&
            meeting.started_at &&
            meeting.ended_at && (
              <span>· {duration(meeting.started_at, meeting.ended_at)}</span>
            )}
        </div>
      </div>

      {/* Status badge */}
      <span
        className={`hidden sm:flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full font-medium shrink-0 ${sm.color}`}
      >
        <span className={`w-1.5 h-1.5 rounded-full ${sm.dot}`} />
        {sm.label}
      </span>

      {/* Actions */}
      <div className="flex items-center gap-2 shrink-0">
        {isLive && (
          <button
            onClick={() => onJoin(meeting.id)}
            disabled={joining === meeting.id}
            className="px-3 py-1.5 text-xs font-medium bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 disabled:opacity-60 transition-colors"
          >
            {joining === meeting.id ? "Opening..." : "Join"}
          </button>
        )}
        {isLive && canEnd && (
          <button
            onClick={() => onEnd(meeting.id)}
            disabled={ending === meeting.id}
            className="px-3 py-1.5 text-xs font-medium border border-red-200 text-red-600 rounded-lg hover:bg-red-50 disabled:opacity-60 transition-colors"
          >
            {ending === meeting.id ? "..." : "End"}
          </button>
        )}
        {isScheduled && (
          <button
            onClick={() => onStart(meeting.id)}
            className="px-3 py-1.5 text-xs font-medium bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors"
          >
            Start Now
          </button>
        )}
        {isScheduled && (
          <button
            onClick={() => onCancel(meeting.id)}
            className="px-3 py-1.5 text-xs font-medium border border-red-200 text-red-600 rounded-lg hover:bg-red-50 transition-colors"
          >
            Cancel
          </button>
        )}
        <button
          onClick={() => onView(meeting)}
          className="px-3 py-1.5 text-xs font-medium border border-slate-200 text-slate-600 rounded-lg hover:bg-slate-50 transition-colors"
        >
          Details
        </button>
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
          <span
            className={`text-xs px-2.5 py-1 rounded-full font-medium ${tm.color}`}
          >
            {tm.label}
          </span>
          {meeting.record && (
            <span className="text-xs px-2.5 py-1 rounded-full bg-slate-100 text-slate-600 font-medium">
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
          <div>
            <span className="text-slate-400 text-xs uppercase tracking-wider font-semibold">
              Created by
            </span>
            <p className="text-slate-800 font-medium mt-0.5">
              {meeting.created_by?.full_name ?? "—"}
            </p>
            {meeting.created_by?.role && (
              <p className="text-slate-400 text-xs mt-0.5 capitalize">
                {meeting.created_by.role.toLowerCase().replace("_", " ")}
              </p>
            )}
          </div>
          {(meeting.class_name || meeting.section_name) && (
            <div>
              <span className="text-slate-400 text-xs uppercase tracking-wider font-semibold">
                Class
              </span>
              <p className="text-slate-800 font-medium mt-0.5">
                {meeting.class_name}
                {meeting.section_name ? ` — ${meeting.section_name}` : ""}
              </p>
            </div>
          )}
          {meeting.teacher_name && (
            <div>
              <span className="text-slate-400 text-xs uppercase tracking-wider font-semibold">
                Teacher
              </span>
              <p className="text-slate-800 font-medium mt-0.5">
                {meeting.teacher_name}
              </p>
            </div>
          )}
        </div>

        {meeting.recording_url && (
          <div className="bg-violet-50 border border-violet-200 rounded-xl p-4">
            <p className="text-xs font-semibold text-violet-700 mb-2">
              Recording Available
            </p>
            <a
              href={meeting.recording_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-violet-600 underline break-all"
            >
              {meeting.recording_url}
            </a>
          </div>
        )}
      </div>
    </Modal>
  );
}

function FiltersBar({
  typeFilter,
  setTypeFilter,
  search,
  setSearch,
}: {
  typeFilter: MeetingType | "";
  setTypeFilter: (v: MeetingType | "") => void;
  search: string;
  setSearch: (v: string) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      {/* Search */}
      <div className="relative">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search meetings..."
          className="pl-3 pr-3 py-2 text-sm border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-slate-300 bg-white w-56"
        />
      </div>

      {/* Type filter */}
      <div className="flex gap-1 bg-slate-100 rounded-xl p-1">
        {(
          [
            ["", "All Types"],
            ["teacher_class", "Class"],
            ["admin_teachers", "Staff"],
          ] as [MeetingType | "", string][]
        ).map(([val, label]) => (
          <button
            key={val}
            onClick={() => setTypeFilter(val)}
            className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-all ${
              typeFilter === val
                ? "bg-white text-slate-900 shadow-sm"
                : "text-slate-500 hover:text-slate-700"
            }`}
          >
            {label}
          </button>
        ))}
      </div>
    </div>
  );
}

type Tab = "live" | "scheduled" | "all" | "past";

export default function AdminMeetingsPage() {
  const auth = getSavedAuth();
  const currentUserId: number = auth?.user?.id ?? 0;

  const [activeTab, setActiveTab] = useState<Tab>("live");
  const [typeFilter, setTypeFilter] = useState<MeetingType | "">("");
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [skip, setSkip] = useState(0);
  const limit = 20;

  const [meetings, setMeetings] = useState<MeetingListOut | null>(null);
  const [stats, setStats] = useState<StatsOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [statsLoading, setStatsLoading] = useState(true);
  const [error, setError] = useState("");

  const meetingsRef = useRef<MeetingListOut | null>(null);

  const [creatingStaff, setCreatingStaff] = useState(false);
  const [launchUrl, setLaunchUrl] = useState<string | null>(null);
  const [viewingMeeting, setViewingMeeting] = useState<MeetingOut | null>(null);
  const [endingId, setEndingId] = useState<number | null>(null);
  const [joining, setJoining] = useState<number | null>(null);
  const [ending, setEnding] = useState<number | null>(null);

  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 350);
    return () => clearTimeout(t);
  }, [search]);

  useEffect(() => {
    setSkip(0);
    setMeetings(null);
    meetingsRef.current = null;
  }, [activeTab, typeFilter, debouncedSearch]);

  const fetchStats = useCallback(async () => {
    setStatsLoading(true);
    try {
      const data = await apiFetch<StatsOut>("/meetings/stats");
      setStats(data);
    } catch {
    } finally {
      setStatsLoading(false);
    }
  }, []);

  const fetchMeetings = useCallback(async () => {
    if (!meetingsRef.current) {
      setLoading(true);
    } else {
      setRefreshing(true);
    }
    setError("");
    try {
      const params = new URLSearchParams({
        skip: String(skip),
        limit: String(limit),
      });
      if (activeTab === "live") params.set("status", "live");
      if (activeTab === "past") params.set("status", "ended");
      if (activeTab === "scheduled") params.set("status", "scheduled");
      if (typeFilter) params.set("meeting_type", typeFilter);
      if (debouncedSearch.trim()) params.set("search", debouncedSearch.trim());

      const data = await apiFetch<MeetingListOut>(`/meetings/?${params}`);
      setMeetings(data);
      meetingsRef.current = data;
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [activeTab, typeFilter, debouncedSearch, skip]);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  useEffect(() => {
    fetchMeetings();
  }, [fetchMeetings]);

  useEffect(() => {
    if (activeTab !== "live") return;
    const interval = setInterval(fetchMeetings, 60000);
    return () => clearInterval(interval);
  }, [activeTab, fetchMeetings]);

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
      setEndingId(null);
      fetchMeetings();
      fetchStats();
    } catch (e: any) {
      alert(e.message);
    } finally {
      setEnding(null);
    }
  }

  function handleCreated(joinUrl: string) {
    setCreatingStaff(false);
    setLaunchUrl(joinUrl);
    fetchMeetings();
    fetchStats();
  }

  async function handleStart(meetingId: number) {
    try {
      const data = await apiFetch<CreateMeetingResponse>(
        `/meetings/${meetingId}/start`,
        { method: "POST" },
      );
      fetchMeetings();
      setLaunchUrl(data.join_url);
    } catch (e: any) {
      alert(e.message);
    }
  }

  async function handleCancel(meetingId: number) {
    try {
      await apiFetch(`/meetings/${meetingId}/cancel`, { method: "DELETE" });
      fetchMeetings();
    } catch (e: any) {
      alert(e.message);
    }
  }

  const totalPages = meetings ? Math.ceil(meetings.total / limit) : 0;
  const currentPage = Math.floor(skip / limit) + 1;
  const liveCount = stats?.live_now ?? 0;

  const TABS: [Tab, string][] = [
    ["live", "Live Now"],
    ["scheduled", "Scheduled"],
    ["all", "All Meetings"],
    ["past", "Past Meetings"],
  ];

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Meetings</h1>
            <p className="text-sm text-slate-500 mt-0.5">
              Manage all live sessions and staff meetings across your school
            </p>
          </div>
          <button
            onClick={() => setCreatingStaff(true)}
            className="flex items-center gap-2 px-4 py-2.5 bg-slate-900 text-white text-sm font-medium rounded-xl hover:bg-slate-700 transition-colors"
          >
            Start Staff Meeting
          </button>
        </div>

        {/* Stats */}
        <StatsRow stats={stats} loading={statsLoading} />

        {/* Tabs */}
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex gap-1 bg-slate-100 rounded-xl p-1 w-fit">
            {TABS.map(([tab, label]) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-5 py-2 text-sm font-medium rounded-lg transition-all ${
                  activeTab === tab
                    ? "bg-white text-slate-900 shadow-sm"
                    : "text-slate-500 hover:text-slate-700"
                }`}
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

          <FiltersBar
            typeFilter={typeFilter}
            setTypeFilter={setTypeFilter}
            search={search}
            setSearch={setSearch}
          />
        </div>

        {/* List */}
        <div className="space-y-2">
          {loading && (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <div
                  key={i}
                  className="h-20 bg-white rounded-2xl border border-slate-100 animate-pulse"
                />
              ))}
            </div>
          )}

          {error && (
            <div className="text-center py-16">
              <p className="text-red-600 text-sm font-medium mb-3">{error}</p>
              <button
                onClick={fetchMeetings}
                className="text-sm text-blue-600 underline"
              >
                Try again
              </button>
            </div>
          )}

          {!loading && !error && meetings && (
            <div
              className={`space-y-2 transition-opacity duration-200 ${
                refreshing ? "opacity-50" : "opacity-100"
              }`}
            >
              {meetings.items.length === 0 ? (
                <div className="text-center py-24 bg-white rounded-2xl border border-slate-100">
                  <p className="text-slate-600 text-lg font-medium mb-2">
                    {activeTab === "live"
                      ? "No live sessions right now"
                      : activeTab === "past"
                        ? "No past meetings yet"
                        : "No meetings found"}
                  </p>
                  <p className="text-slate-400 text-sm mb-6">
                    {activeTab === "live"
                      ? "Teachers can start class meetings from their dashboard"
                      : "Completed sessions will appear here"}
                  </p>
                  {activeTab === "live" && (
                    <button
                      onClick={() => setCreatingStaff(true)}
                      className="px-5 py-2.5 bg-slate-900 text-white text-sm font-medium rounded-xl hover:bg-slate-700 transition-colors"
                    >
                      Start a Staff Meeting
                    </button>
                  )}
                </div>
              ) : (
                <>
                  <div className="hidden md:flex items-center gap-4 px-5 py-2 text-xs font-semibold text-slate-400 uppercase tracking-wider">
                    <div className="w-24 shrink-0" />
                    <div className="flex-1">Meeting</div>
                    <div className="w-24 text-center">Status</div>
                    <div className="w-32 text-right">Actions</div>
                  </div>

                  {meetings.items.map((m) => (
                    <MeetingRow
                      key={m.id}
                      meeting={m}
                      currentUserId={currentUserId}
                      onJoin={handleJoin}
                      onEnd={(id) => setEndingId(id)}
                      onView={setViewingMeeting}
                      joining={joining}
                      ending={ending}
                      currentUserRole={auth?.user?.role ?? ""}
                      onStart={handleStart}
                      onCancel={handleCancel}
                    />
                  ))}
                </>
              )}

              {totalPages > 1 && (
                <div className="flex items-center justify-between pt-4">
                  <p className="text-xs text-slate-400">
                    Showing {skip + 1}–{Math.min(skip + limit, meetings.total)}{" "}
                    of {meetings.total}
                  </p>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setSkip((s) => Math.max(0, s - limit))}
                      disabled={skip === 0}
                      className="px-4 py-2 text-sm border border-slate-200 rounded-xl disabled:opacity-40 hover:bg-slate-50 transition-colors bg-white font-medium"
                    >
                      Previous
                    </button>
                    <span className="text-sm text-slate-600 font-medium">
                      {currentPage} / {totalPages}
                    </span>
                    <button
                      onClick={() => setSkip((s) => s + limit)}
                      disabled={skip + limit >= meetings.total}
                      className="px-4 py-2 text-sm border border-slate-200 rounded-xl disabled:opacity-40 hover:bg-slate-50 transition-colors bg-white font-medium"
                    >
                      Next
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Modals */}

      {creatingStaff && (
        <Modal
          title="Start Staff Meeting"
          onClose={() => setCreatingStaff(false)}
        >
          <StaffMeetingForm
            onClose={() => setCreatingStaff(false)}
            onCreated={handleCreated}
            onScheduled={() => {
              setCreatingStaff(false);
              setActiveTab("scheduled");
            }}
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
            <h3 className="font-semibold text-slate-800">End this meeting?</h3>
            <p className="text-sm text-slate-500">
              All participants will be removed from the session immediately.
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setEndingId(null)}
                className="flex-1 py-2.5 text-sm border border-slate-200 rounded-xl hover:bg-slate-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => handleEnd(endingId)}
                disabled={ending === endingId}
                className="flex-1 py-2.5 text-sm bg-red-600 text-white rounded-xl hover:bg-red-700 disabled:opacity-60 transition-colors font-medium"
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

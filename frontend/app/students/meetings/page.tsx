"use client";

import AppShell from "@/components/AppShell";
import { useState, useEffect, useCallback } from "react";
import { getSavedAuth } from "@/lib/api";
import { apiFetch } from "@/lib/api";

type MeetingType = "teacher_class" | "admin_teachers";
type MeetingStatus = "scheduled" | "live" | "ended";

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

const TYPE_META: Record<MeetingType, { label: string }> = {
  teacher_class: { label: "Class Session" },
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

function timeAgo(dt: string | null): string {
  if (!dt) return "";
  const ms = Date.now() - new Date(dt).getTime();
  const mins = Math.floor(ms / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return fmt(dt);
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

function LiveCard({
  meeting,
  onJoin,
  joining,
}: {
  meeting: MeetingOut;
  onJoin: (id: number) => void;
  joining: number | null;
}) {
  const tm = TYPE_META[meeting.meeting_type];

  return (
    <div className="relative bg-white rounded-2xl border-2 border-emerald-300 shadow-emerald-100 shadow-lg overflow-hidden">
      <div className="h-1 bg-gradient-to-r from-emerald-400 to-teal-400" />
      <div className="p-5">
        <div className="flex items-center justify-between mb-4">
          <span className="flex items-center gap-1.5 text-xs font-bold text-emerald-700 bg-emerald-100 px-2.5 py-1 rounded-full">
            <span className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse" />
            LIVE NOW
          </span>
          <span className="text-xs text-slate-400 font-medium">
            {timeAgo(meeting.started_at ?? meeting.created_at)}
          </span>
        </div>
        <h3 className="font-bold text-slate-900 text-lg mb-1 leading-tight">
          {meeting.title}
        </h3>
        <div className="space-y-1 mb-5">
          <div className="flex items-center gap-2 text-sm text-slate-500">
            <span>{tm.label}</span>
            {meeting.class_name && (
              <>
                <span className="text-slate-300">·</span>
                <span className="font-medium text-slate-700">
                  {meeting.class_name}
                  {meeting.section_name ? ` — ${meeting.section_name}` : ""}
                </span>
              </>
            )}
          </div>
          {meeting.teacher_name && (
            <div className="text-sm text-slate-500">{meeting.teacher_name}</div>
          )}
          {meeting.record && (
            <div className="text-xs text-slate-400">
              This session is being recorded
            </div>
          )}
        </div>
        <button
          onClick={() => onJoin(meeting.id)}
          disabled={joining === meeting.id}
          className="w-full py-3 bg-emerald-600 text-white rounded-xl font-semibold text-sm hover:bg-emerald-700 disabled:opacity-60 active:scale-[0.98] transition-all"
        >
          {joining === meeting.id ? (
            <span className="flex items-center justify-center gap-2">
              <span className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
              Opening...
            </span>
          ) : (
            "Join Session"
          )}
        </button>
      </div>
    </div>
  );
}

function ScheduledCard({ meeting }: { meeting: MeetingOut }) {
  const tm = TYPE_META[meeting.meeting_type];

  return (
    <div className="bg-white rounded-2xl border border-blue-200 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[10px] font-bold px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full">
              UPCOMING
            </span>
          </div>
          <h3 className="font-semibold text-slate-800 text-sm truncate">
            {meeting.title}
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            {tm.label}
            {meeting.class_name ? ` · ${meeting.class_name}` : ""}
            {meeting.teacher_name ? ` · ${meeting.teacher_name}` : ""}
          </p>
        </div>
        <div className="text-right shrink-0">
          <p className="text-xs font-semibold text-blue-700">
            {fmtTime(meeting.scheduled_at)}
          </p>
        </div>
      </div>
    </div>
  );
}

function PastCard({
  meeting,
  onView,
}: {
  meeting: MeetingOut;
  onView: (m: MeetingOut) => void;
}) {
  const tm = TYPE_META[meeting.meeting_type];

  return (
    <div
      onClick={() => onView(meeting)}
      className="group bg-white rounded-2xl border border-slate-200 p-5 cursor-pointer hover:shadow-md hover:-translate-y-0.5 transition-all duration-200"
    >
      <div className="flex items-start gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2 mb-1">
            <h3 className="font-semibold text-slate-800 truncate text-sm leading-tight">
              {meeting.title}
            </h3>
            {meeting.recording_url && (
              <span className="text-[10px] font-bold px-2 py-0.5 bg-violet-100 text-violet-700 rounded-full shrink-0">
                REC
              </span>
            )}
          </div>
          <div className="text-xs text-slate-400 space-y-0.5">
            <p>
              {tm.label}
              {meeting.class_name ? ` · ${meeting.class_name}` : ""}
              {meeting.teacher_name ? ` · ${meeting.teacher_name}` : ""}
            </p>
            <p>
              {fmt(meeting.ended_at ?? meeting.created_at)}
              {meeting.started_at && meeting.ended_at && (
                <span className="ml-2 text-slate-300">
                  · {duration(meeting.started_at, meeting.ended_at)}
                </span>
              )}
            </p>
          </div>
        </div>
        <span className="text-slate-300 group-hover:text-slate-500 transition-colors text-sm shrink-0 mt-1">
          →
        </span>
      </div>
    </div>
  );
}

function PastDetailModal({
  meeting,
  onClose,
  onJoinRecording,
}: {
  meeting: MeetingOut;
  onClose: () => void;
  onJoinRecording: (url: string) => void;
}) {
  const tm = TYPE_META[meeting.meeting_type];

  return (
    <Modal title={meeting.title} onClose={onClose}>
      <div className="space-y-5">
        <div className="flex flex-wrap gap-2">
          <span className="text-xs px-2.5 py-1 rounded-full bg-slate-100 text-slate-600 font-medium">
            {tm.label}
          </span>
          <span className="text-xs px-2.5 py-1 rounded-full bg-slate-100 text-slate-500 font-medium">
            Ended
          </span>
          {meeting.record && (
            <span className="text-xs px-2.5 py-1 rounded-full bg-violet-100 text-violet-700 font-medium">
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
              {fmtTime(meeting.started_at)}
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
          {meeting.class_name && (
            <div className="col-span-2">
              <span className="text-slate-400 text-xs uppercase tracking-wider font-semibold">
                Class
              </span>
              <p className="text-slate-800 font-medium mt-0.5">
                {meeting.class_name}
                {meeting.section_name ? ` — ${meeting.section_name}` : ""}
              </p>
            </div>
          )}
        </div>

        {meeting.recording_url ? (
          <div className="bg-violet-50 border border-violet-200 rounded-xl p-4 space-y-3">
            <div>
              <p className="text-sm font-semibold text-violet-900">
                Recording available
              </p>
              <p className="text-xs text-violet-600 mt-0.5">
                Watch the full session at your own pace
              </p>
            </div>
            <button
              onClick={() => onJoinRecording(meeting.recording_url!)}
              className="w-full py-2.5 bg-violet-600 text-white rounded-xl text-sm font-medium hover:bg-violet-700 transition-colors"
            >
              Watch Recording
            </button>
          </div>
        ) : (
          <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 text-center">
            <p className="text-sm text-slate-500">
              {meeting.record
                ? "Recording is being processed and will be available soon."
                : "No recording for this session."}
            </p>
          </div>
        )}
      </div>
    </Modal>
  );
}

function EmptyState({ tab }: { tab: "live" | "past" }) {
  return (
    <div className="text-center py-24">
      <p className="text-slate-600 text-lg font-medium mb-2">
        {tab === "live" ? "No live sessions right now" : "No past sessions yet"}
      </p>
      <p className="text-slate-400 text-sm">
        {tab === "live"
          ? "Your teacher will start a session when class begins"
          : "Completed sessions and recordings will appear here"}
      </p>
    </div>
  );
}

type Tab = "live" | "past";

export default function StudentMeetingsPage() {
  const [activeTab, setActiveTab] = useState<Tab>("live");
  const [skip, setSkip] = useState(0);
  const limit = 12;

  const [liveMeetings, setLiveMeetings] = useState<MeetingListOut | null>(null);
  const [pastMeetings, setPastMeetings] = useState<MeetingListOut | null>(null);
  const [scheduledMeetings, setScheduledMeetings] =
    useState<MeetingListOut | null>(null);

  const [liveLoading, setLiveLoading] = useState(true);
  const [pastLoading, setPastLoading] = useState(false);
  const [scheduledLoading, setScheduledLoading] = useState(true);

  const [liveError, setLiveError] = useState("");
  const [pastError, setPastError] = useState("");

  const [viewingMeeting, setViewingMeeting] = useState<MeetingOut | null>(null);
  const [joining, setJoining] = useState<number | null>(null);

  const fetchLive = useCallback(async () => {
    setLiveLoading(true);
    setLiveError("");
    try {
      const data = await apiFetch<MeetingListOut>(
        "/meetings/?status=live&limit=20",
      );
      setLiveMeetings(data);
    } catch (e: any) {
      setLiveError(e.message);
    } finally {
      setLiveLoading(false);
    }
  }, []);

  const fetchScheduled = useCallback(async () => {
    setScheduledLoading(true);
    try {
      const data = await apiFetch<MeetingListOut>(
        "/meetings/?status=scheduled&limit=20",
      );
      setScheduledMeetings(data);
    } catch {
      // fail silently
    } finally {
      setScheduledLoading(false);
    }
  }, []);

  const fetchPast = useCallback(async () => {
    setPastLoading(true);
    setPastError("");
    try {
      const params = new URLSearchParams({
        status: "ended",
        skip: String(skip),
        limit: String(limit),
      });
      const data = await apiFetch<MeetingListOut>(`/meetings/?${params}`);
      setPastMeetings(data);
    } catch (e: any) {
      setPastError(e.message);
    } finally {
      setPastLoading(false);
    }
  }, [skip]);

  useEffect(() => {
    fetchLive();
    fetchScheduled();
  }, [fetchLive, fetchScheduled]);

  // poll live every 60s
  useEffect(() => {
    if (activeTab !== "live") return;
    const interval = setInterval(fetchLive, 60000);
    return () => clearInterval(interval);
  }, [activeTab, fetchLive]);

  // poll scheduled every 5 minutes
  useEffect(() => {
    if (activeTab !== "live") return;
    const interval = setInterval(fetchScheduled, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, [activeTab, fetchScheduled]);

  useEffect(() => {
    if (activeTab === "past") fetchPast();
  }, [activeTab, fetchPast]);

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

  const liveCount = liveMeetings?.items.length ?? 0;
  const scheduledCount = scheduledMeetings?.items.length ?? 0;
  const pastPages = pastMeetings ? Math.ceil(pastMeetings.total / limit) : 0;
  const pastPage = Math.floor(skip / limit) + 1;

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-slate-900">My Classes</h1>
          {liveCount > 0 ? (
            <p className="text-sm text-emerald-600 font-medium mt-0.5">
              {liveCount} live {liveCount === 1 ? "session" : "sessions"}{" "}
              happening now
            </p>
          ) : (
            <p className="text-sm text-slate-400 mt-0.5">
              Live sessions and class recordings
            </p>
          )}
        </div>

        {/* Tabs */}
        <div className="flex gap-1 bg-slate-100 rounded-xl p-1 w-fit">
          {(
            [
              ["live", "Live Now"],
              ["past", "Past Sessions"],
            ] as [Tab, string][]
          ).map(([tab, label]) => (
            <button
              key={tab}
              onClick={() => {
                setActiveTab(tab);
                setSkip(0);
              }}
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

        {/* Live Tab */}
        {activeTab === "live" && (
          <div className="space-y-4">
            {liveLoading && (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
                {Array.from({ length: 3 }).map((_, i) => (
                  <div
                    key={i}
                    className="h-56 bg-white rounded-2xl border border-slate-200 animate-pulse"
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

            {!liveLoading && !liveError && liveMeetings && (
              <>
                {liveMeetings.items.length === 0 ? (
                  scheduledCount > 0 ? (
                    <div className="text-center py-12">
                      <p className="text-slate-600 text-lg font-medium mb-1">
                        No live sessions right now
                      </p>
                      <p className="text-slate-400 text-sm">
                        Check the upcoming sessions below
                      </p>
                    </div>
                  ) : (
                    <EmptyState tab="live" />
                  )
                ) : (
                  <>
                    <div className="flex items-center gap-3 bg-emerald-50 border border-emerald-200 rounded-xl px-4 py-3">
                      <p className="text-sm text-emerald-800">
                        <span className="font-semibold">
                          Class is in session!
                        </span>{" "}
                        Join now to attend live.
                      </p>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
                      {liveMeetings.items.map((m) => (
                        <LiveCard
                          key={m.id}
                          meeting={m}
                          onJoin={handleJoin}
                          joining={joining}
                        />
                      ))}
                    </div>
                  </>
                )}

                {!scheduledLoading && scheduledCount > 0 && (
                  <div className="space-y-3 mt-2">
                    <h2 className="text-sm font-semibold text-slate-600 uppercase tracking-wider">
                      Coming Up
                    </h2>
                    <div className="space-y-2">
                      {scheduledMeetings!.items.map((m) => (
                        <ScheduledCard key={m.id} meeting={m} />
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* Past Tab */}
        {activeTab === "past" && (
          <div className="space-y-3">
            {pastLoading && (
              <div className="space-y-3">
                {Array.from({ length: 5 }).map((_, i) => (
                  <div
                    key={i}
                    className="h-20 bg-white rounded-2xl border border-slate-100 animate-pulse"
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
                <EmptyState tab="past" />
              ) : (
                <>
                  <div className="text-xs text-slate-500 bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5">
                    Sessions marked{" "}
                    <span className="font-semibold text-violet-600">REC</span>{" "}
                    have recordings you can watch anytime.
                  </div>
                  <div className="space-y-2">
                    {pastMeetings.items.map((m) => (
                      <PastCard
                        key={m.id}
                        meeting={m}
                        onView={setViewingMeeting}
                      />
                    ))}
                  </div>
                  {pastPages > 1 && (
                    <div className="flex items-center justify-center gap-3 mt-4">
                      <button
                        onClick={() => setSkip((s) => Math.max(0, s - limit))}
                        disabled={skip === 0}
                        className="px-4 py-2 text-sm border border-slate-200 rounded-xl disabled:opacity-40 hover:bg-slate-50 transition-colors bg-white font-medium"
                      >
                        Previous
                      </button>
                      <span className="text-sm text-slate-600 font-medium">
                        Page {pastPage} of {pastPages}
                      </span>
                      <button
                        onClick={() => setSkip((s) => s + limit)}
                        disabled={skip + limit >= (pastMeetings?.total ?? 0)}
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

      {viewingMeeting && (
        <PastDetailModal
          meeting={viewingMeeting}
          onClose={() => setViewingMeeting(null)}
          onJoinRecording={(url) => window.open(url, "_blank")}
        />
      )}
    </AppShell>
  );
}

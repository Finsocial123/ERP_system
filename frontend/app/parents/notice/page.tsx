"use client";

import AppShell from "@/components/AppShell";
import { useState, useEffect, useCallback } from "react";
import { apiFetch } from "@/lib/api";
import ReactMarkdown from "react-markdown";

type NoticePriority = "LOW" | "NORMAL" | "HIGH" | "URGENT";

interface AuthorOut {
  id: number;
  full_name: string;
  role: string;
}

interface NoticeAudienceOut {
  id: number;
  role: string;
}

interface NoticeOut {
  id: number;
  title: string;
  content: string;
  priority: NoticePriority;
  status: string;
  is_pinned: boolean;
  publish_at: string | null;
  expires_at: string | null;
  created_at: string;
  updated_at: string;
  author: AuthorOut | null;
  audiences: NoticeAudienceOut[];
  read_count: number;
  is_read: boolean;
}

interface NoticeListOut {
  items: NoticeOut[];
  total: number;
  unread_count: number;
}

const PRIORITY_META: Record<
  NoticePriority,
  { label: string; color: string; dot: string }
> = {
  LOW: {
    label: "Low",
    color: "bg-slate-100 text-slate-600",
    dot: "bg-slate-400",
  },
  NORMAL: {
    label: "Normal",
    color: "bg-blue-50 text-blue-700",
    dot: "bg-blue-400",
  },
  HIGH: {
    label: "High",
    color: "bg-amber-50 text-amber-700",
    dot: "bg-amber-400",
  },
  URGENT: {
    label: "Urgent",
    color: "bg-red-50 text-red-700",
    dot: "bg-red-500",
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

//modal

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
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />
      <div className="relative w-full max-w-2xl bg-white rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200">
          <h2 className="text-xl font-bold text-slate-800">{title}</h2>
          <button
            onClick={onClose}
            className="w-9 h-9 flex items-center justify-center rounded-full hover:bg-slate-100 text-slate-500 hover:text-slate-700 transition-colors"
          >
            X
          </button>
        </div>
        <div className="overflow-y-auto flex-1 px-6 py-6">{children}</div>
      </div>
    </div>
  );
}

//notice card

function NoticeCard({
  notice,
  onView,
}: {
  notice: NoticeOut;
  onView: (n: NoticeOut) => void;
}) {
  const pm = PRIORITY_META[notice.priority] ?? PRIORITY_META.NORMAL;
  return (
    <div
      onClick={() => onView(notice)}
      className={`group relative bg-white rounded-2xl border cursor-pointer transition-all duration-200 hover:shadow-lg hover:-translate-y-1 ${
        notice.is_pinned
          ? "border-amber-300 shadow-amber-100 shadow-md"
          : notice.is_read
            ? "border-slate-200"
            : "border-blue-300 shadow-blue-50 shadow-sm"
      }`}
    >
      {notice.is_pinned && (
        <div className="absolute -top-2.5 left-4 bg-amber-500 text-white text-[10px] font-bold px-2.5 py-0.5 rounded-full shadow-sm">
          Pinned
        </div>
      )}
      {!notice.is_read && !notice.is_pinned && (
        <div className="absolute -top-2 -right-2 w-8 h-5 bg-blue-500 rounded-full flex items-center justify-center shadow-sm">
          <span className="text-white text-[9px] font-bold">NEW</span>
        </div>
      )}

      <div className="p-5">
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex-1 min-w-0">
            <h3
              className={`font-semibold truncate mb-1 ${notice.is_read ? "text-slate-800" : "text-blue-900"}`}
            >
              {notice.title}
            </h3>
            <p className="text-xs text-slate-400">
              {notice.author?.full_name ?? "School"} · {fmt(notice.created_at)}
            </p>
          </div>
          <span
            className={`flex items-center gap-1.5 text-xs px-3 py-1 rounded-full font-medium shrink-0 ${pm.color}`}
          >
            <span className={`w-2 h-2 rounded-full ${pm.dot}`} />
            {pm.label}
          </span>
        </div>

        {/* <p className="text-sm text-slate-600 line-clamp-2 mb-4 leading-relaxed">
          {notice.content}
        </p> */}
        <div className="text-sm text-slate-600 line-clamp-2 mb-4 leading-relaxed prose-notice">
          <ReactMarkdown>{notice.content}</ReactMarkdown>
        </div>

        <div className="flex items-center justify-end text-xs">
          <span className="flex items-center gap-1 text-blue-600 font-medium group-hover:text-blue-700">
            Read more{" "}
            <span className="group-hover:translate-x-0.5 transition-transform">
              →
            </span>
          </span>
        </div>
      </div>
    </div>
  );
}

//notice modal

function NoticeViewModal({
  notice,
  onClose,
  onMarkRead,
}: {
  notice: NoticeOut;
  onClose: () => void;
  onMarkRead: (id: number) => void;
}) {
  const pm = PRIORITY_META[notice.priority] ?? PRIORITY_META.NORMAL;

  useEffect(() => {
    if (!notice.is_read) onMarkRead(notice.id);
  }, [notice.id, notice.is_read, onMarkRead]);

  return (
    <Modal title={notice.title} onClose={onClose}>
      <div className="space-y-5">
        <div className="flex flex-wrap gap-2">
          <span
            className={`flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-full font-medium ${pm.color}`}
          >
            <span className={`w-2 h-2 rounded-full ${pm.dot}`} />
            {pm.label} Priority
          </span>
          {notice.is_pinned && (
            <span className="text-sm px-3 py-1.5 rounded-full bg-amber-100 text-amber-800 font-medium">
              Pinned
            </span>
          )}
        </div>

        <div className="grid grid-cols-2 gap-4 text-sm bg-slate-50 rounded-xl p-4">
          <div>
            <span className="text-slate-500 text-xs uppercase tracking-wider font-semibold">
              Posted by
            </span>
            <p className="text-slate-800 font-medium mt-0.5">
              {notice.author?.full_name ?? "School Administration"}
            </p>
          </div>
          <div>
            <span className="text-slate-500 text-xs uppercase tracking-wider font-semibold">
              Posted on
            </span>
            <p className="text-slate-800 font-medium mt-0.5">
              {fmtTime(notice.created_at)}
            </p>
          </div>
          {notice.expires_at && (
            <div>
              <span className="text-slate-500 text-xs uppercase tracking-wider font-semibold">
                Expires at
              </span>
              <p className="text-slate-800 font-medium mt-0.5">
                {fmtTime(notice.expires_at)}
              </p>
            </div>
          )}
        </div>

        <div className="bg-slate-50 rounded-xl p-6 border border-slate-200 prose-notice">
          <ReactMarkdown>{notice.content}</ReactMarkdown>
        </div>

        <div className="text-right text-xs text-slate-400 pt-3 border-t border-slate-100">
          Last updated {fmt(notice.updated_at)}
        </div>
      </div>
    </Modal>
  );
}

// main

export default function ParentNotices() {
  const [data, setData] = useState<NoticeListOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [priorityFilter, setPriorityFilter] = useState<NoticePriority | "">("");
  const [showUnreadOnly, setShowUnreadOnly] = useState(false);
  const [skip, setSkip] = useState(0);
  const [viewing, setViewing] = useState<NoticeOut | null>(null);
  const limit = 12;

  const fetchNotices = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({
        skip: String(skip),
        limit: String(limit),
        status: "PUBLISHED",
        pinned_only: "false",
      });

      if (priorityFilter) params.set("priority", priorityFilter);
      if (showUnreadOnly) params.set("unread_only", "true");

      const result = await apiFetch<NoticeListOut>(`/notices/?${params}`);
      setData(result);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [skip, priorityFilter, showUnreadOnly]);

  useEffect(() => {
    setSkip(0);
  }, [priorityFilter, showUnreadOnly]);

  useEffect(() => {
    fetchNotices();
  }, [fetchNotices]);

  async function handleMarkRead(id: number) {
    try {
      await apiFetch(`/notices/${id}/read`, { method: "POST" });
      setData((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          items: prev.items.map((n) =>
            n.id === id ? { ...n, is_read: true } : n,
          ),
          unread_count: Math.max(0, prev.unread_count - 1),
        };
      });
      setViewing((prev) => (prev ? { ...prev, is_read: true } : null));
    } catch (e: any) {
      console.error("Failed to mark as read:", e.message);
    }
  }

  const totalPages = data ? Math.ceil(data.total / limit) : 0;
  const currentPage = Math.floor(skip / limit) + 1;

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Notice Board</h1>
            {data && (
              <p className="text-sm text-slate-500 mt-0.5">
                {data.unread_count > 0 ? (
                  <>
                    <span className="font-semibold text-blue-600">
                      {data.unread_count} unread
                    </span>{" "}
                    {data.unread_count === 1 ? "notice" : "notices"}
                  </>
                ) : (
                  "You are all caught up"
                )}
              </p>
            )}
          </div>
          {data && data.unread_count > 0 && (
            <div className="bg-blue-500 text-white px-4 py-1.5 rounded-full text-sm font-bold shadow">
              {data.unread_count} Unread
            </div>
          )}
        </div>

        {/* Filters */}
        <div className="bg-white rounded-2xl border border-slate-200 p-4 flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Priority:
            </span>
            <div className="flex gap-1.5 flex-wrap">
              {(
                [
                  ["", "All"],
                  ["LOW", "Low"],
                  ["NORMAL", "Normal"],
                  ["HIGH", "High"],
                  ["URGENT", "Urgent"],
                ] as [NoticePriority | "", string][]
              ).map(([val, label]) => (
                <button
                  key={val}
                  onClick={() => setPriorityFilter(val)}
                  className={`text-xs px-3 py-1.5 rounded-full border transition-all font-medium ${
                    priorityFilter === val
                      ? "bg-blue-600 text-white border-blue-600"
                      : "border-slate-200 text-slate-600 hover:border-blue-300 bg-white"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          <div className="w-px h-6 bg-slate-200 hidden sm:block" />

          <label className="flex items-center gap-2.5 cursor-pointer select-none">
            <div
              onClick={() => setShowUnreadOnly((v) => !v)}
              className={`w-11 h-6 rounded-full transition-colors relative ${showUnreadOnly ? "bg-blue-500" : "bg-slate-300"}`}
            >
              <div
                className={`absolute top-1 w-4 h-4 bg-white rounded-full shadow transition-transform ${showUnreadOnly ? "translate-x-6" : "translate-x-1"}`}
              />
            </div>
            <span className="text-sm text-slate-700 font-medium">
              Unread only
            </span>
          </label>
        </div>

        {loading && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {Array.from({ length: 6 }).map((_, i) => (
              <div
                key={i}
                className="h-52 bg-white rounded-2xl border border-slate-200 animate-pulse"
              />
            ))}
          </div>
        )}

        {error && (
          <div className="text-center py-20">
            <p className="text-red-600 text-sm font-medium mb-3">{error}</p>
            <button
              onClick={fetchNotices}
              className="text-sm text-blue-600 underline"
            >
              Try again
            </button>
          </div>
        )}

        {!loading && !error && data && (
          <>
            {data.items.length === 0 ? (
              <div className="text-center py-24">
                <p className="text-slate-600 text-lg font-medium mb-2">
                  {showUnreadOnly ? "No unread notices" : "No notices yet"}
                </p>
                <p className="text-slate-400 text-sm">
                  {showUnreadOnly
                    ? "You have read all your notices"
                    : "Check back later for updates"}
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                {data.items.map((notice) => (
                  <NoticeCard
                    key={notice.id}
                    notice={notice}
                    onView={setViewing}
                  />
                ))}
              </div>
            )}

            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-3 mt-6">
                <button
                  onClick={() => setSkip((s) => Math.max(0, s - limit))}
                  disabled={skip === 0}
                  className="px-4 py-2 text-sm border border-slate-200 rounded-xl disabled:opacity-40 hover:bg-slate-50 transition-colors bg-white font-medium"
                >
                  Previous
                </button>
                <span className="text-sm text-slate-600 font-medium">
                  Page {currentPage} of {totalPages}
                </span>
                <button
                  onClick={() => setSkip((s) => s + limit)}
                  disabled={skip + limit >= (data?.total ?? 0)}
                  className="px-4 py-2 text-sm border border-slate-200 rounded-xl disabled:opacity-40 hover:bg-slate-50 transition-colors bg-white font-medium"
                >
                  Next
                </button>
              </div>
            )}
          </>
        )}
      </div>

      {viewing && (
        <NoticeViewModal
          notice={viewing}
          onClose={() => setViewing(null)}
          onMarkRead={handleMarkRead}
        />
      )}
    </AppShell>
  );
}

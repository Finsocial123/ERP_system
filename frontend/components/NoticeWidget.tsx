"use client";

import { useState, useEffect } from "react";
import { apiFetch, getSavedAuth } from "@/lib/api";
import { useRouter } from "next/navigation";

type NoticePriority = "LOW" | "NORMAL" | "HIGH" | "URGENT";

interface AuthorOut {
  id: number;
  full_name: string;
  role: string;
}

interface NoticeOut {
  id: number;
  title: string;
  content: string;
  priority: NoticePriority;
  is_pinned: boolean;
  created_at: string;
  expires_at: string | null;
  author: AuthorOut | null;
  is_read: boolean;
}

interface NoticeListOut {
  items: NoticeOut[];
  total: number;
  unread_count: number;
}

const PRIORITY_ICONS: Record<NoticePriority, string> = {
  LOW: "",
  NORMAL: "",
  HIGH: "",
  URGENT: "",
};

const ADMIN_ROLES = ["SUPER_ADMIN", "SCHOOL_OWNER", "SCHOOL_ADMIN"];

function noticePathForCurrentRole() {
  const role = getSavedAuth()?.user?.role;

  if (role === "TEACHER") return "/teachers/notice";
  if (role === "PARENT") return "/parents/notice";
  if (ADMIN_ROLES.includes(role ?? "")) return "/setup/notice";

  return "/students/notice";
}

function fmt(dt: string) {
  const date = new Date(dt);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
  });
}

export default function NoticeWidget() {
  const router = useRouter();
  const [data, setData] = useState<NoticeListOut | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchNotices() {
      try {
        const result = await apiFetch<NoticeListOut>(
          "/notices/?limit=5&status=PUBLISHED",
        );
        setData(result);
      } catch (e) {
        console.error("Failed to fetch notices:", e);
      } finally {
        setLoading(false);
      }
    }
    fetchNotices();
  }, []);

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
    } catch (e) {
      console.error("Failed to mark as read:", e);
    }
  }

  if (loading) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-slate-200 rounded w-1/3" />
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-16 bg-slate-100 rounded-xl" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (!data || data.items.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-slate-800">📢 Notices</h2>
        </div>
        <div className="text-center py-8">
          <p className="text-3xl mb-2">📋</p>
          <p className="text-slate-400 text-sm">No notices yet</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-bold text-slate-800">📢 Notices</h2>
          {data.unread_count > 0 && (
            <span className="bg-blue-500 text-white text-xs font-bold px-2 py-0.5 rounded-full">
              {data.unread_count}
            </span>
          )}
        </div>
        <button
          onClick={() => router.push(noticePathForCurrentRole())}
          className="text-sm text-blue-600 hover:text-blue-700 font-medium"
        >
          View all →
        </button>
      </div>

      <div className="space-y-2">
        {data.items.map((notice) => (
          <div
            key={notice.id}
            onClick={() => {
              handleMarkRead(notice.id);
              router.push(noticePathForCurrentRole());
            }}
            className={`group p-3 rounded-xl border cursor-pointer transition-all hover:shadow-md ${
              notice.is_read
                ? "border-slate-200 hover:border-slate-300 bg-white"
                : "border-blue-200 bg-blue-50 hover:border-blue-300"
            }`}
          >
            <div className="flex items-start gap-3">
              <span className="text-xl shrink-0">
                {PRIORITY_ICONS[notice.priority]}
              </span>
              <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between gap-2 mb-1">
                  <h3
                    className={`text-sm font-semibold text-slate-800 line-clamp-1 ${!notice.is_read ? "text-blue-900" : ""}`}
                  >
                    {notice.title}
                  </h3>
                  {!notice.is_read && (
                    <span className="bg-blue-500 text-white text-[9px] font-bold px-1.5 py-0.5 rounded-full shrink-0">
                      NEW
                    </span>
                  )}
                </div>
                <p className="text-xs text-slate-500 line-clamp-1 mb-1">
                  {notice.content}
                </p>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-400">
                    {fmt(notice.created_at)}
                  </span>
                  {notice.is_pinned && (
                    <span className="text-xs text-amber-600">📌 Pinned</span>
                  )}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {data.total > 5 && (
        <button
          onClick={() => router.push(noticePathForCurrentRole())}
          className="w-full mt-3 py-2 text-sm text-slate-600 hover:text-slate-800 font-medium border border-slate-200 rounded-xl hover:bg-slate-50 transition-colors"
        >
          See {data.total - 5} more notices
        </button>
      )}
    </div>
  );
}

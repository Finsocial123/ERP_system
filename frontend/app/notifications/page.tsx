"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Bell, BookOpen, CalendarCheck, CheckCircle2, ClipboardList, GraduationCap, Megaphone, Users } from "lucide-react";

import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";

type Priority = "LOW" | "NORMAL" | "HIGH" | "URGENT";

type NotificationItem = {
  id: number;
  title: string;
  message: string;
  category: string | null;
  priority: Priority;
  target_role: string | null;
  target_user_id: number | null;
  link: string | null;
  expires_at: string | null;
  created_at: string;
  is_read: boolean;
};

type CategoryKey = "ALL" | "HOMEWORK" | "EXAM_REPORT" | "ATTENDANCE" | "MEETING" | "COURSE" | "ANNOUNCEMENT" | "GENERAL";

const categories: { key: CategoryKey; label: string; description: string; icon: typeof Bell }[] = [
  { key: "ALL", label: "All", description: "Everything in one place", icon: Bell },
  { key: "HOMEWORK", label: "Homework", description: "Assigned, submitted, checked", icon: ClipboardList },
  { key: "EXAM_REPORT", label: "Exam Report", description: "Marks and report cards", icon: GraduationCap },
  { key: "ATTENDANCE", label: "Attendance", description: "Absence and attendance alerts", icon: CalendarCheck },
  { key: "MEETING", label: "Meeting", description: "PTM, online class, staff meeting", icon: Users },
  { key: "COURSE", label: "New Courses", description: "Course and LMS updates", icon: BookOpen },
  { key: "ANNOUNCEMENT", label: "Announcements", description: "School notices and updates", icon: Megaphone },
  { key: "GENERAL", label: "General", description: "Other notifications", icon: Bell },
];

const priorityClass: Record<Priority, string> = {
  LOW: "bg-slate-100 text-slate-700",
  NORMAL: "bg-blue-50 text-blue-700",
  HIGH: "bg-amber-50 text-amber-700",
  URGENT: "bg-red-50 text-red-700",
};

function normalizeCategory(value?: string | null): CategoryKey {
  const raw = String(value || "GENERAL").toUpperCase().replaceAll(" ", "_").replaceAll("-", "_");
  if (["HOMEWORK", "ASSIGNMENT"].includes(raw)) return "HOMEWORK";
  if (["EXAM", "EXAMS", "RESULT", "RESULTS", "REPORT", "REPORT_CARD", "EXAM_REPORT"].includes(raw)) return "EXAM_REPORT";
  if (["ATTENDANCE", "ABSENCE", "PRESENT", "LEAVE"].includes(raw)) return "ATTENDANCE";
  if (["MEETING", "EVENT", "PTM", "ONLINE_CLASS"].includes(raw)) return "MEETING";
  if (["COURSE", "COURSES", "LMS", "LESSON", "NEW_COURSE"].includes(raw)) return "COURSE";
  if (["ANNOUNCEMENT", "NOTICE", "NEWS"].includes(raw)) return "ANNOUNCEMENT";
  return "GENERAL";
}

function labelCategory(value?: string | null) {
  const key = normalizeCategory(value);
  return categories.find((item) => item.key === key)?.label || "General";
}

function fmtDateTime(value?: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleString("en-IN", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

function EmptyState({ category }: { category: string }) {
  return (
    <div className="rounded-3xl border border-dashed border-slate-300 bg-white p-10 text-center shadow-sm">
      <Bell className="mx-auto text-slate-300" size={40} />
      <h2 className="mt-4 text-lg font-bold text-slate-900">No {category.toLowerCase()} notifications</h2>
      <p className="mt-1 text-sm text-slate-500">When homework, exam reports, attendance, meetings, courses or notices are published, they will appear here.</p>
    </div>
  );
}

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [activeCategory, setActiveCategory] = useState<CategoryKey>("ALL");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadNotifications = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    setError("");
    try {
      const data = await apiFetch<NotificationItem[]>("/communication/notifications?limit=100");
      setNotifications(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load notifications.");
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadNotifications();
  }, [loadNotifications]);

  useEffect(() => {
    const refreshSilently = () => void loadNotifications(true);
    const interval = window.setInterval(refreshSilently, 30000);
    window.addEventListener("erp_notifications_updated", refreshSilently);
    window.addEventListener("focus", refreshSilently);
    return () => {
      window.clearInterval(interval);
      window.removeEventListener("erp_notifications_updated", refreshSilently);
      window.removeEventListener("focus", refreshSilently);
    };
  }, [loadNotifications]);

  const counts = useMemo(() => {
    const next: Record<CategoryKey, number> = { ALL: notifications.length, HOMEWORK: 0, EXAM_REPORT: 0, ATTENDANCE: 0, MEETING: 0, COURSE: 0, ANNOUNCEMENT: 0, GENERAL: 0 };
    notifications.forEach((item) => {
      next[normalizeCategory(item.category)] += 1;
    });
    return next;
  }, [notifications]);

  const unreadCount = notifications.filter((item) => !item.is_read).length;
  const filteredNotifications = activeCategory === "ALL" ? notifications : notifications.filter((item) => normalizeCategory(item.category) === activeCategory);

  async function markRead(id: number) {
    await apiFetch(`/communication/notifications/${id}/read`, { method: "POST" });
    await loadNotifications(true);
  }

  async function markAllRead() {
    await apiFetch("/communication/notifications/read-all", { method: "POST" });
    await loadNotifications(true);
  }

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="flex items-center gap-2 text-sm font-bold uppercase tracking-wide text-slate-400"><Bell size={16} /> Notifications</p>
            <h1 className="mt-2 text-3xl font-black text-slate-950">Notification Center</h1>
            <p className="mt-1 text-slate-500">Homework, exam reports, attendance, meetings, new courses, announcements and general alerts.</p>
          </div>
          <button onClick={() => void markAllRead()} disabled={!notifications.length || unreadCount === 0} className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-5 py-3 text-sm font-bold text-slate-700 shadow-sm hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50">
            <CheckCircle2 size={16} /> Mark all read
          </button>
        </div>

        <div className="grid gap-3 md:grid-cols-4 xl:grid-cols-8">
          {categories.map((category) => {
            const Icon = category.icon;
            const active = activeCategory === category.key;
            return (
              <button
                key={category.key}
                onClick={() => setActiveCategory(category.key)}
                className={`rounded-3xl border p-4 text-left shadow-sm transition ${active ? "border-slate-900 bg-slate-900 text-white" : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"}`}
              >
                <div className="mb-3 flex items-center justify-between gap-2">
                  <Icon size={18} className={active ? "text-white" : "text-slate-500"} />
                  <span className={`rounded-full px-2 py-0.5 text-xs font-black ${active ? "bg-white/15 text-white" : "bg-slate-100 text-slate-700"}`}>{counts[category.key]}</span>
                </div>
                <p className="text-sm font-black">{category.label}</p>
                <p className={`mt-1 text-xs ${active ? "text-white/70" : "text-slate-400"}`}>{category.description}</p>
              </button>
            );
          })}
        </div>

        {error && <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>}
        {loading ? (
          <div className="rounded-3xl border border-slate-200 bg-white p-8 text-sm text-slate-500 shadow-sm">Loading notifications...</div>
        ) : filteredNotifications.length === 0 ? (
          <EmptyState category={categories.find((item) => item.key === activeCategory)?.label || "selected"} />
        ) : (
          <div className="space-y-3">
            {filteredNotifications.map((item) => (
              <article key={item.id} className={`rounded-3xl border p-5 shadow-sm ${item.is_read ? "border-slate-200 bg-white" : "border-blue-200 bg-blue-50"}`}>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded-full bg-slate-900 px-2.5 py-1 text-xs font-bold text-white">{labelCategory(item.category)}</span>
                      <span className={`rounded-full px-2.5 py-1 text-xs font-bold ${priorityClass[item.priority]}`}>{item.priority}</span>
                      {!item.is_read && <span className="rounded-full bg-blue-600 px-2.5 py-1 text-xs font-bold text-white">NEW</span>}
                    </div>
                    <h2 className="mt-3 text-lg font-black text-slate-950">{item.title}</h2>
                    <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-slate-600">{item.message}</p>
                    <p className="mt-3 text-xs font-semibold text-slate-400">{fmtDateTime(item.created_at)}</p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {item.link && <Link href={item.link} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-700 hover:bg-slate-50">Open</Link>}
                    {!item.is_read && <button onClick={() => void markRead(item.id)} className="rounded-xl border border-blue-200 bg-white px-3 py-2 text-xs font-bold text-blue-700 hover:bg-blue-50">Mark read</button>}
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}

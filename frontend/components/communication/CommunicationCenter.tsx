"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { apiFetch, getSavedAuth } from "@/lib/api";

type UserRole = "SCHOOL_OWNER" | "SCHOOL_ADMIN" | "TEACHER" | "STUDENT" | "PARENT";
type Priority = "LOW" | "NORMAL" | "HIGH" | "URGENT";
type PublishStatus = "DRAFT" | "PUBLISHED" | "ARCHIVED";
type ComplaintStatus = "SUBMITTED" | "UNDER_REVIEW" | "RESOLVED" | "REJECTED" | "CLOSED";
type TabKey = "overview" | "announcements" | "events" | "complaints" | "notifications";

type UserMini = { id: number; full_name: string; role: string };

type Overview = {
  announcements: number;
  upcoming_events: number;
  open_complaints: number;
  unread_notifications: number;
};

type Announcement = {
  id: number;
  title: string;
  message: string;
  priority: Priority;
  status: PublishStatus;
  audience_roles: string[];
  start_at: string | null;
  end_at: string | null;
  created_at: string;
  updated_at: string;
  author: UserMini | null;
};

type SchoolEvent = {
  id: number;
  title: string;
  description: string | null;
  event_date: string;
  end_date: string | null;
  start_time: string | null;
  end_time: string | null;
  location: string | null;
  category: string | null;
  status: PublishStatus;
  audience_roles: string[];
  created_at: string;
  updated_at: string;
  author: UserMini | null;
};

type Complaint = {
  id: number;
  subject: string;
  description: string;
  category: string | null;
  priority: Priority;
  status: ComplaintStatus;
  action_taken: string | null;
  is_anonymous: boolean;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
  creator: UserMini | null;
  assignee: UserMini | null;
};

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
  author: UserMini | null;
};

const audienceRoles: UserRole[] = ["TEACHER", "STUDENT", "PARENT"];
const priorities: Priority[] = ["LOW", "NORMAL", "HIGH", "URGENT"];
const publishStatuses: PublishStatus[] = ["DRAFT", "PUBLISHED", "ARCHIVED"];

const priorityClass: Record<Priority, string> = {
  LOW: "bg-slate-100 text-slate-700",
  NORMAL: "bg-blue-50 text-blue-700",
  HIGH: "bg-amber-50 text-amber-700",
  URGENT: "bg-red-50 text-red-700",
};

const statusClass: Record<string, string> = {
  DRAFT: "bg-slate-100 text-slate-700",
  PUBLISHED: "bg-emerald-50 text-emerald-700",
  ARCHIVED: "bg-orange-50 text-orange-700",
  RESOLVED: "bg-emerald-50 text-emerald-700",
  CLOSED: "bg-slate-100 text-slate-700",
  SUBMITTED: "bg-blue-50 text-blue-700",
  UNDER_REVIEW: "bg-violet-50 text-violet-700",
  REJECTED: "bg-red-50 text-red-700",
};

function today() {
  return new Date().toISOString().slice(0, 10);
}

function fmtDate(value?: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

function fmtDateTime(value?: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

function fmtTime(value?: string | null) {
  if (!value) return "";
  return value.slice(0, 5);
}

function roleLabel(role: string) {
  return role.replaceAll("_", " ").toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
}

function Badge({ value, tone }: { value: string; tone?: Record<string, string> }) {
  return <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${tone?.[value] || "bg-slate-100 text-slate-700"}`}>{roleLabel(value)}</span>;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block space-y-1.5">
      <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</span>
      {children}
    </label>
  );
}

function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={`w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none transition focus:border-slate-400 ${props.className || ""}`} />;
}

function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={`w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none transition focus:border-slate-400 ${props.className || ""}`} />;
}

function Textarea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={`w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none transition focus:border-slate-400 ${props.className || ""}`} />;
}

function AudienceSelector({ value, onChange }: { value: UserRole[]; onChange: (roles: UserRole[]) => void }) {
  function toggle(role: UserRole) {
    onChange(value.includes(role) ? value.filter((item) => item !== role) : [...value, role]);
  }

  return (
    <div className="flex flex-wrap gap-2">
      {audienceRoles.map((role) => (
        <button
          type="button"
          key={role}
          onClick={() => toggle(role)}
          className={`rounded-full border px-3 py-1 text-xs font-semibold transition ${value.includes(role) ? "border-slate-900 bg-slate-900 text-white" : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"}`}
        >
          {roleLabel(role)}
        </button>
      ))}
      <button type="button" onClick={() => onChange([])} className="rounded-full border border-slate-200 px-3 py-1 text-xs font-semibold text-slate-600 hover:bg-slate-50">All roles</button>
    </div>
  );
}

function EmptyState({ title }: { title: string }) {
  return <div className="rounded-2xl border border-dashed border-slate-200 bg-white p-8 text-center text-sm text-slate-500">{title}</div>;
}

export default function CommunicationCenter() {
  const auth = getSavedAuth();
  const role = auth?.user.role || "";
  const isAdmin = ["SUPER_ADMIN", "SCHOOL_OWNER", "SCHOOL_ADMIN"].includes(role);
  const [activeTab, setActiveTab] = useState<TabKey>("overview");
  const [loadingTab, setLoadingTab] = useState<TabKey | "">("");
  const loadedTabsRef = useRef<Partial<Record<TabKey, boolean>>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const [overview, setOverview] = useState<Overview | null>(null);
  const [announcements, setAnnouncements] = useState<Announcement[]>([]);
  const [events, setEvents] = useState<SchoolEvent[]>([]);
  const [complaints, setComplaints] = useState<Complaint[]>([]);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);

  const [announcementForm, setAnnouncementForm] = useState({ title: "", message: "", priority: "NORMAL" as Priority, status: "PUBLISHED" as PublishStatus, audience_roles: [] as UserRole[], start_at: "", end_at: "" });
  const [eventForm, setEventForm] = useState({ title: "", description: "", event_date: today(), end_date: "", start_time: "", end_time: "", location: "", category: "", status: "PUBLISHED" as PublishStatus, audience_roles: [] as UserRole[] });
  const [complaintForm, setComplaintForm] = useState({ subject: "", description: "", category: "", priority: "NORMAL" as Priority, is_anonymous: false });
  const [notificationForm, setNotificationForm] = useState({ title: "", message: "", category: "GENERAL", priority: "NORMAL" as Priority, target_role: "" as "" | UserRole, target_user_id: "", link: "/notifications", expires_at: "" });

  const tabs = useMemo(
    () => [
      ["overview", "Overview"],
      ["announcements", "Announcements"],
      ["events", "Event Calendar"],
      ["complaints", "Complaints"],
      ["notifications", "Notifications"],
    ] as [TabKey, string][],
    [],
  );

  const loadTab = useCallback(async (tab: TabKey, force = false) => {
    if (!force && loadedTabsRef.current[tab]) return;
    setLoadingTab(tab);
    setError("");
    try {
      if (tab === "overview") {
        setOverview(await apiFetch<Overview>("/communication/overview"));
      } else if (tab === "announcements") {
        setAnnouncements(await apiFetch<Announcement[]>("/communication/announcements"));
      } else if (tab === "events") {
        setEvents(await apiFetch<SchoolEvent[]>("/communication/events"));
      } else if (tab === "complaints") {
        setComplaints(await apiFetch<Complaint[]>("/communication/complaints"));
      } else if (tab === "notifications") {
        setNotifications(await apiFetch<NotificationItem[]>("/communication/notifications"));
      }
      loadedTabsRef.current[tab] = true;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load communication data.");
    } finally {
      setLoadingTab((current) => (current === tab ? "" : current));
    }
  }, []);

  useEffect(() => {
    void loadTab(activeTab);
  }, [activeTab, loadTab]);

  async function refreshAfterWrite(tab: TabKey) {
    loadedTabsRef.current[tab] = false;
    loadedTabsRef.current.overview = false;
    await loadTab(tab, true);
    if (tab !== "overview") {
      void loadTab("overview", true);
    }
  }

  async function submitForm(path: string, payload: unknown, reset: () => void, refreshTab: TabKey = activeTab) {
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      await apiFetch(path, { method: "POST", body: JSON.stringify(payload) });
      reset();
      setSuccess("Saved successfully.");
      await refreshAfterWrite(refreshTab);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed.");
    } finally {
      setSaving(false);
    }
  }

  async function patchItem(path: string, payload: unknown, refreshTab: TabKey = activeTab) {
    setSaving(true);
    setError("");
    try {
      await apiFetch(path, { method: "PATCH", body: JSON.stringify(payload) });
      await refreshAfterWrite(refreshTab);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed.");
    } finally {
      setSaving(false);
    }
  }

  async function markRead(id: number) {
    await apiFetch(`/communication/notifications/${id}/read`, { method: "POST" });
    await refreshAfterWrite("notifications");
  }

  async function markAllRead() {
    await apiFetch("/communication/notifications/read-all", { method: "POST" });
    await refreshAfterWrite("notifications");
  }

  const statCards = [
    ["Announcements", overview?.announcements ?? 0],
    ["Upcoming Events", overview?.upcoming_events ?? 0],
    ["Open Complaints", overview?.open_complaints ?? 0],
    ["Unread Notifications", overview?.unread_notifications ?? 0],
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-bold uppercase tracking-wide text-slate-400">Communication</p>
          <h1 className="text-2xl font-bold text-slate-900">Notice & Communication Center</h1>
          <p className="mt-1 text-sm text-slate-500">Announcements, event calendar, complaints and in-app notifications.</p>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {tabs.map(([key, label]) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={`rounded-xl px-4 py-2 text-sm font-semibold transition ${activeTab === key ? "bg-slate-900 text-white" : "border border-slate-200 bg-white text-slate-600 hover:bg-slate-50"}`}
          >
            {label}
          </button>
        ))}
      </div>

      {error && <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>}
      {success && <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-700">{success}</div>}
      {loadingTab === activeTab ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-8 text-sm text-slate-500">Loading...</div>
      ) : (
        <>
          {activeTab === "overview" && (
            <section className="grid gap-4 md:grid-cols-4">
              {statCards.map(([label, value]) => (
                <div key={label} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                  <p className="text-sm font-medium text-slate-500">{label}</p>
                  <p className="mt-2 text-3xl font-black text-slate-900">{value}</p>
                </div>
              ))}
            </section>
          )}

          {activeTab === "announcements" && (
            <section className="space-y-4">
              {isAdmin && (
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    const payload = { ...announcementForm, start_at: announcementForm.start_at || null, end_at: announcementForm.end_at || null };
                    void submitForm("/communication/announcements", payload, () => setAnnouncementForm({ title: "", message: "", priority: "NORMAL", status: "PUBLISHED", audience_roles: [], start_at: "", end_at: "" }));
                  }}
                  className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
                >
                  <h2 className="mb-4 text-lg font-bold text-slate-900">Create Announcement</h2>
                  <div className="grid gap-4 md:grid-cols-2">
                    <Field label="Title"><Input required value={announcementForm.title} onChange={(e) => setAnnouncementForm({ ...announcementForm, title: e.target.value })} /></Field>
                    <Field label="Priority"><Select value={announcementForm.priority} onChange={(e) => setAnnouncementForm({ ...announcementForm, priority: e.target.value as Priority })}>{priorities.map((p) => <option key={p}>{p}</option>)}</Select></Field>
                    <Field label="Status"><Select value={announcementForm.status} onChange={(e) => setAnnouncementForm({ ...announcementForm, status: e.target.value as PublishStatus })}>{publishStatuses.map((s) => <option key={s}>{s}</option>)}</Select></Field>
                    <Field label="Start At"><Input type="datetime-local" value={announcementForm.start_at} onChange={(e) => setAnnouncementForm({ ...announcementForm, start_at: e.target.value })} /></Field>
                    <Field label="End At"><Input type="datetime-local" value={announcementForm.end_at} onChange={(e) => setAnnouncementForm({ ...announcementForm, end_at: e.target.value })} /></Field>
                    <div className="md:col-span-2"><Field label="Audience"><AudienceSelector value={announcementForm.audience_roles} onChange={(roles) => setAnnouncementForm({ ...announcementForm, audience_roles: roles })} /></Field></div>
                    <div className="md:col-span-2"><Field label="Message"><Textarea required rows={4} value={announcementForm.message} onChange={(e) => setAnnouncementForm({ ...announcementForm, message: e.target.value })} /></Field></div>
                  </div>
                  <button disabled={saving} className="mt-4 rounded-xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">Save Announcement</button>
                </form>
              )}
              {announcements.length === 0 ? <EmptyState title="No announcements found" /> : announcements.map((item) => (
                <article key={item.id} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                  <div className="flex flex-wrap items-center gap-2"><h3 className="mr-auto text-lg font-bold text-slate-900">{item.title}</h3><Badge value={item.priority} tone={priorityClass} /><Badge value={item.status} tone={statusClass} /></div>
                  <p className="mt-2 whitespace-pre-wrap text-sm text-slate-600">{item.message}</p>
                  <div className="mt-4 flex flex-wrap gap-3 text-xs text-slate-500"><span>Created: {fmtDateTime(item.created_at)}</span><span>Audience: {item.audience_roles.length ? item.audience_roles.map(roleLabel).join(", ") : "All"}</span></div>
                </article>
              ))}
            </section>
          )}

          {activeTab === "events" && (
            <section className="space-y-4">
              {isAdmin && (
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    const payload = { ...eventForm, end_date: eventForm.end_date || null, start_time: eventForm.start_time || null, end_time: eventForm.end_time || null, location: eventForm.location || null, category: eventForm.category || null };
                    void submitForm("/communication/events", payload, () => setEventForm({ title: "", description: "", event_date: today(), end_date: "", start_time: "", end_time: "", location: "", category: "", status: "PUBLISHED", audience_roles: [] }));
                  }}
                  className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
                >
                  <h2 className="mb-4 text-lg font-bold text-slate-900">Create Event / Meeting</h2>
                  <div className="grid gap-4 md:grid-cols-2">
                    <Field label="Title"><Input required value={eventForm.title} onChange={(e) => setEventForm({ ...eventForm, title: e.target.value })} /></Field>
                    <Field label="Category"><Input value={eventForm.category} onChange={(e) => setEventForm({ ...eventForm, category: e.target.value })} placeholder="Meeting, Exam, Holiday" /></Field>
                    <Field label="Event Date"><Input required type="date" value={eventForm.event_date} onChange={(e) => setEventForm({ ...eventForm, event_date: e.target.value })} /></Field>
                    <Field label="End Date"><Input type="date" value={eventForm.end_date} onChange={(e) => setEventForm({ ...eventForm, end_date: e.target.value })} /></Field>
                    <Field label="Start Time"><Input type="time" value={eventForm.start_time} onChange={(e) => setEventForm({ ...eventForm, start_time: e.target.value })} /></Field>
                    <Field label="End Time"><Input type="time" value={eventForm.end_time} onChange={(e) => setEventForm({ ...eventForm, end_time: e.target.value })} /></Field>
                    <Field label="Location"><Input value={eventForm.location} onChange={(e) => setEventForm({ ...eventForm, location: e.target.value })} /></Field>
                    <Field label="Status"><Select value={eventForm.status} onChange={(e) => setEventForm({ ...eventForm, status: e.target.value as PublishStatus })}>{publishStatuses.map((s) => <option key={s}>{s}</option>)}</Select></Field>
                    <div className="md:col-span-2"><Field label="Audience"><AudienceSelector value={eventForm.audience_roles} onChange={(roles) => setEventForm({ ...eventForm, audience_roles: roles })} /></Field></div>
                    <div className="md:col-span-2"><Field label="Description"><Textarea rows={3} value={eventForm.description} onChange={(e) => setEventForm({ ...eventForm, description: e.target.value })} /></Field></div>
                  </div>
                  <button disabled={saving} className="mt-4 rounded-xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">Save Event</button>
                </form>
              )}
              {events.length === 0 ? <EmptyState title="No events found" /> : events.map((item) => (
                <article key={item.id} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                  <div className="flex flex-wrap items-center gap-2"><h3 className="mr-auto text-lg font-bold text-slate-900">{item.title}</h3><Badge value={item.status} tone={statusClass} /></div>
                  <p className="mt-1 text-sm text-slate-500">{fmtDate(item.event_date)} {fmtTime(item.start_time)} {item.end_time ? `- ${fmtTime(item.end_time)}` : ""} {item.location ? `· ${item.location}` : ""}</p>
                  {item.description && <p className="mt-3 whitespace-pre-wrap text-sm text-slate-600">{item.description}</p>}
                  <div className="mt-4 flex flex-wrap gap-3 text-xs text-slate-500"><span>Category: {item.category || "General"}</span><span>Audience: {item.audience_roles.length ? item.audience_roles.map(roleLabel).join(", ") : "All"}</span></div>
                </article>
              ))}
            </section>
          )}

          {activeTab === "complaints" && (
            <section className="space-y-4">
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  void submitForm("/communication/complaints", { ...complaintForm, category: complaintForm.category || null }, () => setComplaintForm({ subject: "", description: "", category: "", priority: "NORMAL", is_anonymous: false }));
                }}
                className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
              >
                <h2 className="mb-4 text-lg font-bold text-slate-900">Submit Complaint</h2>
                <div className="grid gap-4 md:grid-cols-2">
                  <Field label="Subject"><Input required value={complaintForm.subject} onChange={(e) => setComplaintForm({ ...complaintForm, subject: e.target.value })} /></Field>
                  <Field label="Category"><Input value={complaintForm.category} onChange={(e) => setComplaintForm({ ...complaintForm, category: e.target.value })} placeholder="Discipline, Facility, Transport" /></Field>
                  <Field label="Priority"><Select value={complaintForm.priority} onChange={(e) => setComplaintForm({ ...complaintForm, priority: e.target.value as Priority })}>{priorities.map((p) => <option key={p}>{p}</option>)}</Select></Field>
                  <label className="mt-7 flex items-center gap-2 text-sm font-semibold text-slate-600"><input type="checkbox" checked={complaintForm.is_anonymous} onChange={(e) => setComplaintForm({ ...complaintForm, is_anonymous: e.target.checked })} /> Submit anonymously</label>
                  <div className="md:col-span-2"><Field label="Description"><Textarea required rows={3} value={complaintForm.description} onChange={(e) => setComplaintForm({ ...complaintForm, description: e.target.value })} /></Field></div>
                </div>
                <button disabled={saving} className="mt-4 rounded-xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">Submit Complaint</button>
              </form>
              {complaints.length === 0 ? <EmptyState title="No complaints found" /> : complaints.map((item) => (
                <article key={item.id} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                  <div className="flex flex-wrap items-center gap-2"><h3 className="mr-auto text-lg font-bold text-slate-900">#{item.id} {item.subject}</h3><Badge value={item.priority} tone={priorityClass} /><Badge value={item.status} tone={statusClass} /></div>
                  <p className="mt-2 whitespace-pre-wrap text-sm text-slate-600">{item.description}</p>
                  {item.action_taken && <p className="mt-3 rounded-xl bg-emerald-50 p-3 text-sm text-emerald-800">Action Taken: {item.action_taken}</p>}
                  <div className="mt-4 flex flex-wrap gap-3 text-xs text-slate-500"><span>Created: {fmtDateTime(item.created_at)}</span><span>By: {item.creator?.full_name || (item.is_anonymous ? "Anonymous" : "—")}</span><span>Category: {item.category || "—"}</span></div>
                  {isAdmin && item.status !== "RESOLVED" && item.status !== "CLOSED" && item.status !== "REJECTED" && (
                    <div className="mt-4 flex flex-wrap gap-2">
                      <button onClick={() => void patchItem(`/communication/complaints/${item.id}`, { status: "UNDER_REVIEW" })} className="rounded-xl border border-violet-200 px-3 py-2 text-xs font-semibold text-violet-700 hover:bg-violet-50">Under Review</button>
                      <button onClick={() => void patchItem(`/communication/complaints/${item.id}`, { status: "RESOLVED", action_taken: "Complaint resolved by school admin." })} className="rounded-xl border border-emerald-200 px-3 py-2 text-xs font-semibold text-emerald-700 hover:bg-emerald-50">Resolve</button>
                    </div>
                  )}
                </article>
              ))}
            </section>
          )}

          {activeTab === "notifications" && (
            <section className="space-y-4">
              {isAdmin && (
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    const payload = { ...notificationForm, target_role: notificationForm.target_role || null, target_user_id: notificationForm.target_user_id ? Number(notificationForm.target_user_id) : null, expires_at: notificationForm.expires_at || null };
                    void submitForm("/communication/notifications", payload, () => setNotificationForm({ title: "", message: "", category: "GENERAL", priority: "NORMAL", target_role: "", target_user_id: "", link: "/notifications", expires_at: "" }));
                  }}
                  className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
                >
                  <h2 className="mb-4 text-lg font-bold text-slate-900">Send In-app Notification</h2>
                  <div className="grid gap-4 md:grid-cols-2">
                    <Field label="Title"><Input required value={notificationForm.title} onChange={(e) => setNotificationForm({ ...notificationForm, title: e.target.value })} /></Field>
                    <Field label="Category"><Input value={notificationForm.category} onChange={(e) => setNotificationForm({ ...notificationForm, category: e.target.value.toUpperCase() })} placeholder="HOMEWORK, EXAM_REPORT, ATTENDANCE, MEETING, COURSE" /></Field>
                    <Field label="Priority"><Select value={notificationForm.priority} onChange={(e) => setNotificationForm({ ...notificationForm, priority: e.target.value as Priority })}>{priorities.map((p) => <option key={p}>{p}</option>)}</Select></Field>
                    <Field label="Target Role"><Select value={notificationForm.target_role} onChange={(e) => setNotificationForm({ ...notificationForm, target_role: e.target.value as "" | UserRole })}><option value="">All roles</option>{audienceRoles.map((r) => <option key={r} value={r}>{roleLabel(r)}</option>)}</Select></Field>
                    <Field label="Target User ID"><Input type="number" value={notificationForm.target_user_id} onChange={(e) => setNotificationForm({ ...notificationForm, target_user_id: e.target.value })} placeholder="Optional" /></Field>
                    <Field label="Link"><Input value={notificationForm.link} onChange={(e) => setNotificationForm({ ...notificationForm, link: e.target.value })} /></Field>
                    <Field label="Expires At"><Input type="datetime-local" value={notificationForm.expires_at} onChange={(e) => setNotificationForm({ ...notificationForm, expires_at: e.target.value })} /></Field>
                    <div className="md:col-span-2"><Field label="Message"><Textarea required rows={3} value={notificationForm.message} onChange={(e) => setNotificationForm({ ...notificationForm, message: e.target.value })} /></Field></div>
                  </div>
                  <button disabled={saving} className="mt-4 rounded-xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">Send Notification</button>
                </form>
              )}
              <div className="flex justify-end"><button onClick={() => void markAllRead()} className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50">Mark all read</button></div>
              {notifications.length === 0 ? <EmptyState title="No notifications found" /> : notifications.map((item) => (
                <article key={item.id} className={`rounded-2xl border p-5 shadow-sm ${item.is_read ? "border-slate-200 bg-white" : "border-blue-200 bg-blue-50"}`}>
                  <div className="flex flex-wrap items-center gap-2"><h3 className="mr-auto text-lg font-bold text-slate-900">{item.title}</h3><Badge value={item.priority} tone={priorityClass} />{!item.is_read && <Badge value="NEW" tone={{ NEW: "bg-blue-600 text-white" }} />}</div>
                  <p className="mt-2 whitespace-pre-wrap text-sm text-slate-600">{item.message}</p>
                  <div className="mt-4 flex flex-wrap gap-3 text-xs text-slate-500"><span>Category: {item.category || "GENERAL"}</span><span>Created: {fmtDateTime(item.created_at)}</span><span>Target: {item.target_role ? roleLabel(item.target_role) : "All"}</span></div>
                  {!item.is_read && <button onClick={() => void markRead(item.id)} className="mt-4 rounded-xl border border-blue-200 px-3 py-2 text-xs font-semibold text-blue-700 hover:bg-blue-100">Mark Read</button>}
                </article>
              ))}
            </section>
          )}
        </>
      )}
    </div>
  );
}

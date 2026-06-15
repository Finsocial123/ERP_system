"use client";

import AppShell from "@/components/AppShell";
import { useState, useEffect, useCallback } from "react";
import { apiFetch } from "@/lib/api";
import ReactMarkdown from "react-markdown";
import "@/app/globals.css";

type NoticePriority = "LOW" | "NORMAL" | "HIGH" | "URGENT";
type NoticeStatus = "DRAFT" | "PUBLISHED" | "ARCHIVED";
type AudienceRole = "STUDENT" | "PARENT" | "TEACHER";

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
  school_id: number;
  title: string;
  content: string;
  priority: NoticePriority;
  status: NoticeStatus;
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

const STATUS_META: Record<NoticeStatus, { label: string; color: string }> = {
  DRAFT: { label: "Draft", color: "bg-slate-100 text-slate-600" },
  PUBLISHED: { label: "Published", color: "bg-emerald-50 text-emerald-700" },
  ARCHIVED: { label: "Archived", color: "bg-orange-50 text-orange-600" },
};

const AUDIENCE_ROLES: AudienceRole[] = ["STUDENT", "PARENT", "TEACHER"];

function fmt(dt: string | null) {
  if (!dt) return "—";
  return new Date(dt).toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function fmtDatetimeLocal(dt: string | null) {
  if (!dt) return "";
  const d = new Date(dt);
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
}

interface NoticeFormState {
  title: string;
  content: string;
  priority: NoticePriority;
  status: NoticeStatus;
  publish_at: string;
  expires_at: string;
  audience_roles: AudienceRole[];
  enhance: boolean;
}

function emptyForm(): NoticeFormState {
  return {
    title: "",
    content: "",
    priority: "NORMAL",
    status: "DRAFT",
    publish_at: "",
    expires_at: "",
    audience_roles: ["STUDENT"],
    enhance: false,
  };
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
      <div className="relative w-full max-w-2xl bg-white rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
          <h2 className="text-lg font-semibold text-slate-800">{title}</h2>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-slate-100 text-slate-500 hover:text-slate-700 transition-colors"
          >
            X
          </button>
        </div>
        <div className="overflow-y-auto flex-1 px-6 py-5">{children}</div>
      </div>
    </div>
  );
}

function AIPanel({
  onInsert,
  currentContent,
}: {
  onInsert: (text: string) => void;
  currentContent: string;
}) {
  const [tab, setTab] = useState<"enhance" | "generate">("generate");
  const [description, setDescription] = useState("");
  const [result, setResult] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleGenerate() {
    setError("");
    setResult("");
    setLoading(true);
    try {
      const data = await apiFetch<{ generated: string }>("/notices/generate", {
        method: "POST",
        body: JSON.stringify({ description }),
      });
      setResult(data.generated);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleEnhance() {
    setError("");
    setResult("");
    setLoading(true);
    try {
      const data = await apiFetch<{ enhanced: string }>("/notices/enhance", {
        method: "POST",
        body: JSON.stringify({ content: currentContent }),
      });
      setResult(data.enhanced);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="border border-violet-200 rounded-xl bg-violet-50 p-4 space-y-3">
      <div className="flex items-center gap-2">
        <span className="text-violet-600 font-bold text-sm">AI Assistant</span>
      </div>

      <div className="flex gap-1 bg-violet-100 rounded-lg p-1 w-fit">
        {(["generate", "enhance"] as const).map((t) => (
          <button
            key={t}
            onClick={() => {
              setTab(t);
              setResult("");
              setError("");
            }}
            className={`px-3 py-1 text-xs font-medium rounded-md transition-all ${tab === t ? "bg-white text-violet-700 shadow-sm" : "text-violet-500 hover:text-violet-700"}`}
          >
            {t === "generate"
              ? "Generate from description"
              : "Enhance existing content"}
          </button>
        ))}
      </div>

      {tab === "generate" ? (
        <div className="space-y-2">
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Describe the notice… (e.g. Holi holiday on March 14, classes resume March 17)"
            rows={2}
            className="w-full text-sm border border-violet-200 rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-violet-300 resize-none placeholder:text-slate-400"
          />
          <p className="text-xs text-violet-400">
            Tip: Include specific dates, event name, and any instructions for
            better results.
          </p>
          <button
            onClick={handleGenerate}
            disabled={loading || !description.trim()}
            className="text-xs px-4 py-1.5 bg-violet-600 text-white rounded-lg hover:bg-violet-700 disabled:opacity-50 transition-colors"
          >
            {loading ? "Generating..." : "Generate"}
          </button>
        </div>
      ) : (
        <div className="space-y-2">
          <p className="text-xs text-violet-600">
            Will enhance the content currently in the editor.
          </p>
          <button
            onClick={handleEnhance}
            disabled={loading || !currentContent.trim()}
            className="text-xs px-4 py-1.5 bg-violet-600 text-white rounded-lg hover:bg-violet-700 disabled:opacity-50 transition-colors"
          >
            {loading ? "Enhancing..." : "Enhance"}
          </button>
        </div>
      )}

      {error && <p className="text-xs text-red-600">{error}</p>}

      {result && (
        <div className="bg-white border border-violet-200 rounded-lg p-3 space-y-2">
          <div
            className="text-slate-600 prose-notice"
            style={{ fontSize: "0.78rem" }}
          >
            <ReactMarkdown>{result}</ReactMarkdown>
          </div>
          <button
            onClick={() => onInsert(result)}
            className="text-xs px-3 py-1 bg-violet-600 text-white rounded-md hover:bg-violet-700 transition-colors"
          >
            Use this
          </button>
        </div>
      )}
    </div>
  );
}

function NoticeForm({
  initial,
  onSave,
  onClose,
}: {
  initial?: NoticeOut | null;
  onSave: () => void;
  onClose: () => void;
}) {
  const [form, setForm] = useState<NoticeFormState>(() => {
    if (initial) {
      return {
        title: initial.title,
        content: initial.content,
        priority: initial.priority,
        status: initial.status,
        publish_at: fmtDatetimeLocal(initial.publish_at),
        expires_at: fmtDatetimeLocal(initial.expires_at),
        audience_roles: initial.audiences
          .map((a) => a.role as AudienceRole)
          .filter((r) => AUDIENCE_ROLES.includes(r)),
        enhance: false,
      };
    }
    return emptyForm();
  });

  const [showAI, setShowAI] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const set = (key: string, val: any) => setForm((f) => ({ ...f, [key]: val }));

  function toggleRole(role: AudienceRole) {
    setForm((f) => ({
      ...f,
      audience_roles: f.audience_roles.includes(role)
        ? f.audience_roles.filter((r) => r !== role)
        : [...f.audience_roles, role],
    }));
  }

  const audienceError = form.audience_roles.length === 0;

  async function handleSubmit() {
    if (audienceError) return;
    setError("");
    setLoading(true);
    try {
      const body: Record<string, any> = {
        title: form.title,
        content: form.content,
        priority: form.priority,
        status: form.status,
        publish_at: form.publish_at
          ? new Date(form.publish_at).toISOString()
          : null,
        expires_at: form.expires_at
          ? new Date(form.expires_at).toISOString()
          : null,
        audience_roles: form.audience_roles,
      };
      if (!initial) {
        body.enhance = form.enhance;
      }
      if (initial) {
        await apiFetch(`/notices/${initial.id}`, {
          method: "PATCH",
          body: JSON.stringify(body),
        });
      } else {
        await apiFetch("/notices/", {
          method: "POST",
          body: JSON.stringify(body),
        });
      }
      onSave();
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
          Title
        </label>
        <input
          value={form.title}
          onChange={(e) => set("title", e.target.value)}
          placeholder="Notice title"
          className={inputCls}
        />
      </div>

      <div>
        <div className="flex items-center justify-between mb-1.5">
          <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Content
          </label>
          <button
            onClick={() => setShowAI((v) => !v)}
            className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${showAI ? "bg-violet-600 text-white border-violet-600" : "border-violet-300 text-violet-600 hover:bg-violet-50"}`}
          >
            AI Assistant
          </button>
        </div>
        <textarea
          value={form.content}
          onChange={(e) => set("content", e.target.value)}
          placeholder="Write the notice content..."
          rows={5}
          className={`${inputCls} resize-none`}
        />
      </div>

      {showAI && (
        <AIPanel
          currentContent={form.content}
          onInsert={(text) => set("content", text)}
        />
      )}

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wider">
            Priority
          </label>
          <select
            value={form.priority}
            onChange={(e) => set("priority", e.target.value)}
            className={inputCls}
          >
            {(Object.keys(PRIORITY_META) as NoticePriority[]).map((p) => (
              <option key={p} value={p}>
                {PRIORITY_META[p].label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wider">
            Status
          </label>
          <select
            value={form.status}
            onChange={(e) => set("status", e.target.value)}
            className={inputCls}
          >
            {(Object.keys(STATUS_META) as NoticeStatus[]).map((s) => (
              <option key={s} value={s}>
                {STATUS_META[s].label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wider">
            Publish At
          </label>
          <input
            type="datetime-local"
            value={form.publish_at}
            onChange={(e) => set("publish_at", e.target.value)}
            className={inputCls}
          />
        </div>
        <div>
          <label className="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wider">
            Expires At
          </label>
          <input
            type="datetime-local"
            value={form.expires_at}
            onChange={(e) => set("expires_at", e.target.value)}
            className={inputCls}
          />
        </div>
      </div>

      <div>
        <label className="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wider">
          Send To{" "}
          <span className="text-red-400 font-normal normal-case">
            * at least one required
          </span>
        </label>
        <div className="flex gap-2">
          {AUDIENCE_ROLES.map((role) => (
            <button
              key={role}
              onClick={() => toggleRole(role)}
              className={`flex-1 py-2 text-sm font-medium rounded-xl border transition-all ${
                form.audience_roles.includes(role)
                  ? "bg-slate-900 text-white border-slate-900"
                  : "border-slate-200 text-slate-600 hover:border-slate-400 bg-white"
              }`}
            >
              {role.charAt(0) + role.slice(1).toLowerCase()}
            </button>
          ))}
        </div>
        {audienceError && (
          <p className="text-xs text-red-500 mt-1.5">
            Select at least one audience to publish this notice.
          </p>
        )}
      </div>

      {!initial && (
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={form.enhance}
            onChange={(e) => set("enhance", e.target.checked)}
            className="w-4 h-4 accent-violet-600"
          />
          <span className="text-sm text-slate-600">
            Auto-enhance content with AI before saving
          </span>
        </label>
      )}

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
          onClick={handleSubmit}
          disabled={
            loading ||
            !form.title.trim() ||
            !form.content.trim() ||
            audienceError
          }
          className="flex-1 py-2.5 text-sm bg-slate-900 text-white rounded-xl hover:bg-slate-700 disabled:opacity-50 transition-colors font-medium"
        >
          {loading ? "Saving..." : initial ? "Update Notice" : "Create Notice"}
        </button>
      </div>
    </div>
  );
}

function NoticeCard({
  notice,
  onEdit,
  onDelete,
  onPin,
  onView,
}: {
  notice: NoticeOut;
  onEdit: (n: NoticeOut) => void;
  onDelete: (id: number) => void;
  onPin: (id: number, pinned: boolean) => void;
  onView: (n: NoticeOut) => void;
}) {
  const pm = PRIORITY_META[notice.priority] ?? PRIORITY_META.NORMAL;
  const sm = STATUS_META[notice.status] ?? STATUS_META.DRAFT;

  return (
    <div
      className={`group relative bg-white rounded-2xl border transition-all duration-200 hover:shadow-md hover:-translate-y-0.5 ${
        notice.is_pinned
          ? "border-amber-200 shadow-amber-50 shadow-sm"
          : "border-slate-100"
      }`}
    >
      {notice.is_pinned && (
        <div className="absolute -top-2 left-4 bg-amber-400 text-white text-[10px] font-bold px-2 py-0.5 rounded-full">
          Pinned
        </div>
      )}

      <div className="p-5">
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-slate-800 truncate">
              {notice.title}
            </h3>

            {notice.status === "PUBLISHED" &&
              notice.publish_at &&
              new Date(notice.publish_at) > new Date() && (
                <span className="text-xs px-2 py-0.5 rounded-full bg-blue-50 text-blue-600 font-medium">
                  Scheduled
                </span>
              )}
            <p className="text-xs text-slate-400 mt-0.5">
              {notice.author?.full_name ?? "Unknown"} · {fmt(notice.created_at)}
            </p>
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            <span
              className={`flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium ${pm.color}`}
            >
              <span className={`w-1.5 h-1.5 rounded-full ${pm.dot}`} />
              {pm.label}
            </span>
            <span
              className={`text-xs px-2 py-0.5 rounded-full font-medium ${sm.color}`}
            >
              {sm.label}
            </span>
          </div>
        </div>

        <div className="text-sm text-slate-500 line-clamp-2 mb-4 prose-notice max-w-none">
          <ReactMarkdown>{notice.content}</ReactMarkdown>
        </div>

        <div className="flex items-center justify-between">
          {/* Audience tags */}
          <div className="flex items-center gap-1 flex-wrap">
            {notice.audiences
              .filter((a) => AUDIENCE_ROLES.includes(a.role as AudienceRole))
              .map((a) => (
                <span
                  key={a.id}
                  className="text-[10px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-500 font-medium"
                >
                  {a.role.charAt(0) + a.role.slice(1).toLowerCase()}
                </span>
              ))}
            {notice.expires_at && (
              <span className="text-[10px] text-slate-400 ml-1">
                Expires {fmt(notice.expires_at)}
              </span>
            )}
          </div>

          <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
            <button
              onClick={() => onView(notice)}
              title="View"
              className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-500 hover:text-slate-700 text-xs transition-colors"
            >
              View
            </button>
            <button
              onClick={() => onPin(notice.id, !notice.is_pinned)}
              title={notice.is_pinned ? "Unpin" : "Pin"}
              className="p-1.5 rounded-lg hover:bg-amber-50 text-slate-500 hover:text-amber-600 text-xs transition-colors"
            >
              {notice.is_pinned ? "Unpin" : "Pin"}
            </button>
            <button
              onClick={() => onEdit(notice)}
              title="Edit"
              className="p-1.5 rounded-lg hover:bg-blue-50 text-slate-500 hover:text-blue-600 text-xs transition-colors"
            >
              Edit
            </button>
            <button
              onClick={() => onDelete(notice.id)}
              title="Delete"
              className="p-1.5 rounded-lg hover:bg-red-50 text-slate-500 hover:text-red-600 text-xs transition-colors"
            >
              Delete
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function NoticeViewModal({
  notice,
  onClose,
}: {
  notice: NoticeOut;
  onClose: () => void;
}) {
  const pm = PRIORITY_META[notice.priority] ?? PRIORITY_META.NORMAL;
  const sm = STATUS_META[notice.status] ?? STATUS_META.DRAFT;

  return (
    <Modal title={notice.title} onClose={onClose}>
      <div className="space-y-4">
        <div className="flex flex-wrap gap-2">
          <span
            className={`flex items-center gap-1 text-xs px-2.5 py-1 rounded-full font-medium ${pm.color}`}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${pm.dot}`} />
            {pm.label}
          </span>
          <span
            className={`text-xs px-2.5 py-1 rounded-full font-medium ${sm.color}`}
          >
            {sm.label}
          </span>
          {notice.is_pinned && (
            <span className="text-xs px-2.5 py-1 rounded-full bg-amber-50 text-amber-700 font-medium">
              Pinned
            </span>
          )}
        </div>

        <div className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <span className="text-slate-400 text-xs">Author</span>
            <p className="text-slate-700">{notice.author?.full_name ?? "—"}</p>
          </div>
          <div>
            <span className="text-slate-400 text-xs">Created</span>
            <p className="text-slate-700">{fmt(notice.created_at)}</p>
          </div>
          <div>
            <span className="text-slate-400 text-xs">Publish at</span>
            <p className="text-slate-700">{fmt(notice.publish_at)}</p>
          </div>
          <div>
            <span className="text-slate-400 text-xs">Expires at</span>
            <p className="text-slate-700">{fmt(notice.expires_at)}</p>
          </div>
          <div>
            <span className="text-slate-400 text-xs">Read by</span>
            <p className="text-slate-700">
              {notice.read_count}{" "}
              {notice.read_count === 1 ? "person" : "people"}
            </p>
          </div>
        </div>

        {notice.audiences.length > 0 && (
          <div>
            <span className="text-xs text-slate-400">Sent to</span>
            <div className="flex flex-wrap gap-1.5 mt-1">
              {notice.audiences
                .filter((a) => AUDIENCE_ROLES.includes(a.role as AudienceRole))
                .map((a) => (
                  <span
                    key={a.id}
                    className="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-600"
                  >
                    {a.role.charAt(0) + a.role.slice(1).toLowerCase()}
                  </span>
                ))}
            </div>
          </div>
        )}
        <div className="bg-slate-50 rounded-xl p-4 prose-notice">
          <ReactMarkdown>{notice.content}</ReactMarkdown>
        </div>
      </div>
    </Modal>
  );
}

export default function Notice() {
  const [data, setData] = useState<NoticeListOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [statusFilter, setStatusFilter] = useState<NoticeStatus | "">("");
  const [pinnedOnly, setPinnedOnly] = useState(false);
  const [skip, setSkip] = useState(0);
  const limit = 12;

  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<NoticeOut | null>(null);
  const [viewing, setViewing] = useState<NoticeOut | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const fetchNotices = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({
        skip: String(skip),
        limit: String(limit),
        pinned_only: String(pinnedOnly),
      });
      if (statusFilter) params.set("status", statusFilter);
      const result = await apiFetch<NoticeListOut>(`/notices/?${params}`);
      setData(result);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [skip, statusFilter, pinnedOnly]);

  useEffect(() => {
    fetchNotices();
  }, [fetchNotices]);

  async function handleDelete(id: number) {
    try {
      await apiFetch(`/notices/${id}`, { method: "DELETE" });
      setDeletingId(null);
      fetchNotices();
    } catch (e: any) {
      alert(e.message);
    }
  }

  async function handlePin(id: number, is_pinned: boolean) {
    try {
      await apiFetch(`/notices/${id}/pin`, {
        method: "PATCH",
        body: JSON.stringify({ is_pinned }),
      });
      fetchNotices();
    } catch (e: any) {
      alert(e.message);
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
              <p className="text-sm text-slate-400 mt-0.5">
                {data.total} notices
              </p>
            )}
          </div>
          <button
            onClick={() => setCreating(true)}
            className="flex items-center gap-2 px-4 py-2.5 bg-slate-900 text-white text-sm font-medium rounded-xl hover:bg-slate-700 transition-colors"
          >
            + New Notice
          </button>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="flex gap-1.5">
            {(
              [
                ["", "All"],
                ["DRAFT", "Draft"],
                ["PUBLISHED", "Published"],
                ["ARCHIVED", "Archived"],
              ] as [string, string][]
            ).map(([val, label]) => (
              <button
                key={val}
                onClick={() => {
                  setStatusFilter(val as NoticeStatus | "");
                  setSkip(0);
                }}
                className={`text-xs px-3 py-1.5 rounded-full border transition-all ${
                  statusFilter === val
                    ? "bg-slate-900 text-white border-slate-900"
                    : "border-slate-200 text-slate-600 hover:border-slate-400 bg-white"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          <div className="w-px h-5 bg-slate-200 hidden sm:block" />

          <label className="flex items-center gap-2 cursor-pointer select-none">
            <div
              onClick={() => {
                setPinnedOnly((v) => !v);
                setSkip(0);
              }}
              className={`w-9 h-5 rounded-full transition-colors relative ${pinnedOnly ? "bg-amber-400" : "bg-slate-200"}`}
            >
              <div
                className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${pinnedOnly ? "translate-x-4" : "translate-x-0.5"}`}
              />
            </div>
            <span className="text-xs text-slate-600">Pinned only</span>
          </label>
        </div>

        {loading && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <div
                key={i}
                className="h-44 bg-white rounded-2xl border border-slate-100 animate-pulse"
              />
            ))}
          </div>
        )}

        {error && (
          <div className="text-center py-16">
            <p className="text-red-600 text-sm">{error}</p>
            <button
              onClick={fetchNotices}
              className="mt-3 text-sm text-slate-500 underline"
            >
              Retry
            </button>
          </div>
        )}

        {!loading && !error && data && (
          <>
            {data.items.length === 0 ? (
              <div className="text-center py-24">
                <p className="text-slate-500 text-sm">No notices found</p>
                <button
                  onClick={() => setCreating(true)}
                  className="mt-4 text-sm text-slate-700 underline"
                >
                  Create one
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {data.items.map((notice) => (
                  <NoticeCard
                    key={notice.id}
                    notice={notice}
                    onEdit={setEditing}
                    onDelete={setDeletingId}
                    onPin={handlePin}
                    onView={setViewing}
                  />
                ))}
              </div>
            )}

            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-2 mt-8">
                <button
                  onClick={() => setSkip((s) => Math.max(0, s - limit))}
                  disabled={skip === 0}
                  className="px-3 py-1.5 text-sm border border-slate-200 rounded-lg disabled:opacity-40 hover:bg-slate-50 transition-colors"
                >
                  Previous
                </button>
                <span className="text-sm text-slate-500">
                  Page {currentPage} of {totalPages}
                </span>
                <button
                  onClick={() => setSkip((s) => s + limit)}
                  disabled={skip + limit >= (data?.total ?? 0)}
                  className="px-3 py-1.5 text-sm border border-slate-200 rounded-lg disabled:opacity-40 hover:bg-slate-50 transition-colors"
                >
                  Next
                </button>
              </div>
            )}
          </>
        )}
      </div>

      {/* Modals */}
      {creating && (
        <Modal title="New Notice" onClose={() => setCreating(false)}>
          <NoticeForm
            onClose={() => setCreating(false)}
            onSave={() => {
              setCreating(false);
              fetchNotices();
            }}
          />
        </Modal>
      )}

      {editing && (
        <Modal title="Edit Notice" onClose={() => setEditing(null)}>
          <NoticeForm
            initial={editing}
            onClose={() => setEditing(null)}
            onSave={() => {
              setEditing(null);
              fetchNotices();
            }}
          />
        </Modal>
      )}

      {viewing && (
        <NoticeViewModal notice={viewing} onClose={() => setViewing(null)} />
      )}

      {deletingId !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div
            className="absolute inset-0 bg-black/40 backdrop-blur-sm"
            onClick={() => setDeletingId(null)}
          />
          <div className="relative bg-white rounded-2xl shadow-2xl p-6 w-full max-w-sm text-center space-y-4">
            <h3 className="font-semibold text-slate-800">Delete Notice?</h3>
            <p className="text-sm text-slate-500">
              This action cannot be undone.
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setDeletingId(null)}
                className="flex-1 py-2 text-sm border border-slate-200 rounded-xl hover:bg-slate-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => handleDelete(deletingId)}
                className="flex-1 py-2 text-sm bg-red-600 text-white rounded-xl hover:bg-red-700 transition-colors"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}

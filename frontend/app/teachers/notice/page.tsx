"use client";

import AppShell from "@/components/AppShell";
import { useState, useEffect, useCallback } from "react";
import { getSavedAuth } from "@/lib/api";
import { apiFetch } from "@/lib/api";
import ReactMarkdown from "react-markdown";

type NoticePriority = "LOW" | "NORMAL" | "HIGH" | "URGENT";
type NoticeStatus = "DRAFT" | "PUBLISHED" | "ARCHIVED";
type AudienceRole = "STUDENT" | "PARENT" | "TEACHER";

interface AvailableClass {
  class_id: number;
  class_name: string;
  section_id: number | null;
  section_name: string | null;
}

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

const ALL_AUDIENCE_ROLES: AudienceRole[] = ["STUDENT", "PARENT", "TEACHER"];
const FORM_AUDIENCE_ROLES: AudienceRole[] = ["STUDENT", "PARENT"];

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

function fmtDatetimeLocal(dt: string | null) {
  if (!dt) return "";
  const d = new Date(dt);
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
}

function emptyForm() {
  return {
    title: "",
    content: "",
    priority: "NORMAL" as NoticePriority,
    status: "DRAFT" as NoticeStatus,
    publish_at: "",
    expires_at: "",
    audience_roles: ["STUDENT"] as AudienceRole[],
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
      <span className="text-violet-600 font-bold text-sm">AI Assistant</span>
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
              : "Enhance existing"}
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
            className="w-full text-sm border border-violet-200 rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-violet-300 resize-none"
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
  const [form, setForm] = useState(() => {
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
          .filter((r) => FORM_AUDIENCE_ROLES.includes(r)),
        audience_class_ids: [],
        audience_section_ids: [],
        enhance: false,
      };
    }
    return {
      ...emptyForm(),
      audience_class_ids: [],
      audience_section_ids: [],
    };
  });

  const [availableClasses, setAvailableClasses] = useState<AvailableClass[]>(
    [],
  );
  const [selectedClassPairs, setSelectedClassPairs] = useState<Set<string>>(
    new Set(),
  );
  const [loadingClasses, setLoadingClasses] = useState(false);
  const [showAI, setShowAI] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  function toggleClassPair(classId: number, sectionId: number | null) {
    const key = `${classId}_${sectionId}`;
    setSelectedClassPairs((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }

  useEffect(() => {
    async function fetchClasses() {
      setLoadingClasses(true);
      try {
        const data = await apiFetch<AvailableClass[]>(
          "/teachers/me/available-classes",
        );
        setAvailableClasses(data);
      } catch (e: any) {
        console.error("Failed to fetch classes:", e.message);
      } finally {
        setLoadingClasses(false);
      }
    }
    fetchClasses();
  }, []);

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
      const pairs = Array.from(selectedClassPairs).map((key) => {
        const [classId, sectionId] = key.split("_");
        return {
          class_id: parseInt(classId),
          section_id: sectionId === "null" ? null : parseInt(sectionId),
        };
      });

      const body = {
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
        audience_class_ids: pairs.map((p) => p.class_id),
        audience_section_ids: pairs.map((p) => p.section_id),
        enhance: form.enhance,
      };
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

      {/* Replace the entire audience <div> section with this */}
      <div className="space-y-4">
        <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider">
          Audience
        </label>

        {/* Step 1: Class Selection (teachers only) */}
        {availableClasses.length > 0 && (
          <div className="border border-slate-200 rounded-xl overflow-hidden">
            <div className="px-4 py-3 bg-slate-50 border-b border-slate-200">
              <p className="text-xs font-semibold text-slate-600 uppercase tracking-wider">
                Select Classes
              </p>
              <p className="text-xs text-slate-400 mt-0.5">
                Leave empty to send to all classes
              </p>
            </div>
            {loadingClasses ? (
              <div className="px-4 py-3 text-sm text-slate-400">
                Loading classes...
              </div>
            ) : (
              <div className="p-3 grid grid-cols-2 gap-2 max-h-48 overflow-y-auto">
                {availableClasses.map((cls) => {
                  const key = `${cls.class_id}_${cls.section_id}`;
                  const isSelected = selectedClassPairs.has(key);
                  const label = cls.section_name
                    ? `${cls.class_name} · ${cls.section_name}`
                    : cls.class_name;
                  return (
                    <button
                      key={key}
                      type="button"
                      onClick={() =>
                        toggleClassPair(cls.class_id, cls.section_id)
                      }
                      className={`px-3 py-2 text-sm rounded-lg border transition-all text-left font-medium ${
                        isSelected
                          ? "bg-slate-900 text-white border-slate-900"
                          : "bg-white border-slate-200 text-slate-600 hover:border-slate-400"
                      }`}
                    >
                      {label}
                    </button>
                  );
                })}
              </div>
            )}
            {selectedClassPairs.size > 0 && (
              <div className="px-4 py-2 bg-blue-50 border-t border-blue-100">
                <p className="text-xs text-blue-600 font-medium">
                  {selectedClassPairs.size} class
                  {selectedClassPairs.size > 1 ? "es" : ""} selected
                </p>
              </div>
            )}
          </div>
        )}

        {/* Step 2: Role Selection */}
        <div className="border border-slate-200 rounded-xl overflow-hidden">
          <div className="px-4 py-3 bg-slate-50 border-b border-slate-200">
            <p className="text-xs font-semibold text-slate-600 uppercase tracking-wider">
              {availableClasses.length > 0 ? "Send To" : "Send To"}
            </p>
            <p className="text-xs text-slate-400 mt-0.5">
              Select who should receive this notice
              <span className="text-red-400 ml-1">* required</span>
            </p>
          </div>
          <div className="p-3 flex gap-2">
            {FORM_AUDIENCE_ROLES.map((role) => (
              <button
                key={role}
                type="button"
                onClick={() => toggleRole(role)}
                className={`flex-1 py-2.5 text-sm font-medium rounded-lg border transition-all ${
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
            <div className="px-4 py-2 bg-red-50 border-t border-red-100">
              <p className="text-xs text-red-500">
                Select at least one recipient.
              </p>
            </div>
          )}
        </div>

        {/* Summary */}
        {(selectedClassPairs.size > 0 || form.audience_roles.length > 0) && (
          <div className="flex items-center gap-2 flex-wrap px-1">
            <span className="text-xs text-slate-400">Sending to:</span>
            {selectedClassPairs.size > 0 ? (
              Array.from(selectedClassPairs).map((key) => {
                const [classId, sectionId] = key.split("_");
                const cls = availableClasses.find(
                  (c) =>
                    c.class_id === parseInt(classId) &&
                    String(c.section_id) === sectionId,
                );
                const label = cls
                  ? cls.section_name
                    ? `${cls.class_name} · ${cls.section_name}`
                    : cls.class_name
                  : key;
                return (
                  <span
                    key={key}
                    className="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 font-medium"
                  >
                    {label}
                  </span>
                );
              })
            ) : (
              <span className="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-500">
                All classes
              </span>
            )}
            {form.audience_roles.length > 0 && (
              <>
                <span className="text-xs text-slate-300">→</span>
                {form.audience_roles.map((r) => (
                  <span
                    key={r}
                    className="text-xs px-2 py-0.5 rounded-full bg-blue-50 text-blue-600 font-medium"
                  >
                    {r.charAt(0) + r.slice(1).toLowerCase()}
                  </span>
                ))}
              </>
            )}
          </div>
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

function ReceivedCard({
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

        <div className="flex items-center justify-between text-xs">
          {notice.expires_at ? (
            <span className="text-slate-400">
              Expires {fmt(notice.expires_at)}
            </span>
          ) : (
            <span />
          )}
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

function MyNoticeCard({
  notice,
  onEdit,
  onDelete,
  onView,
}: {
  notice: NoticeOut;
  onEdit: (n: NoticeOut) => void;
  onDelete: (id: number) => void;
  onView: (n: NoticeOut) => void;
}) {
  const pm = PRIORITY_META[notice.priority] ?? PRIORITY_META.NORMAL;
  const sm = STATUS_META[notice.status] ?? STATUS_META.DRAFT;

  return (
    <div className="group relative bg-white rounded-2xl border border-slate-100 transition-all duration-200 hover:shadow-md hover:-translate-y-0.5">
      <div className="p-5">
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-slate-800 truncate">
              {notice.title}
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              {fmt(notice.created_at)}
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

        {/* <p className="text-sm text-slate-500 line-clamp-2 mb-4">
          {notice.content}
        </p> */}
        <div className="text-sm text-slate-500 line-clamp-2 mb-4 prose-notice">
          <ReactMarkdown>{notice.content}</ReactMarkdown>
        </div>

        <div className="flex items-center justify-between">
          <div className="flex gap-1 flex-wrap">
            {notice.audiences
              .filter((a) =>
                ALL_AUDIENCE_ROLES.includes(a.role as AudienceRole),
              )
              .map((a) => (
                <span
                  key={a.id}
                  className="text-[10px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-500 font-medium"
                >
                  {a.role.charAt(0) + a.role.slice(1).toLowerCase()}
                </span>
              ))}
          </div>
          <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
            <button
              onClick={() => onView(notice)}
              className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-500 hover:text-slate-700 text-xs transition-colors"
            >
              View
            </button>
            <button
              onClick={() => onEdit(notice)}
              className="p-1.5 rounded-lg hover:bg-blue-50 text-slate-500 hover:text-blue-600 text-xs transition-colors"
            >
              Edit
            </button>
            <button
              onClick={() => onDelete(notice.id)}
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

function ReceivedViewModal({
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

function MyNoticeViewModal({
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
        </div>

        <div className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <span className="text-slate-400 text-xs">Created</span>
            <p className="text-slate-700">{fmt(notice.created_at)}</p>
          </div>
          <div>
            <span className="text-slate-400 text-xs">Updated</span>
            <p className="text-slate-700">{fmt(notice.updated_at)}</p>
          </div>
          <div>
            <span className="text-slate-400 text-xs">Publish at</span>
            <p className="text-slate-700">{fmt(notice.publish_at)}</p>
          </div>
          <div>
            <span className="text-slate-400 text-xs">Expires at</span>
            <p className="text-slate-700">{fmt(notice.expires_at)}</p>
          </div>
        </div>

        {notice.audiences.length > 0 && (
          <div>
            <span className="text-xs text-slate-400">Sent to</span>
            <div className="flex flex-wrap gap-1.5 mt-1">
              {notice.audiences
                .filter((a) =>
                  ALL_AUDIENCE_ROLES.includes(a.role as AudienceRole),
                )
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

type Tab = "received" | "mine";

export default function TeacherNotice() {
  const auth = getSavedAuth();

  const currentUserRole: string | undefined = auth?.user?.role;
  const isAdmin = currentUserRole
    ? ["SUPER_ADMIN", "SCHOOL_OWNER", "SCHOOL_ADMIN"].includes(currentUserRole)
    : false;

  const [activeTab, setActiveTab] = useState<Tab>("received");

  const [received, setReceived] = useState<NoticeListOut | null>(null);
  const [receivedLoading, setReceivedLoading] = useState(true);
  const [receivedError, setReceivedError] = useState("");
  const [receivedSkip, setReceivedSkip] = useState(0);
  const [viewingReceived, setViewingReceived] = useState<NoticeOut | null>(
    null,
  );

  const [mine, setMine] = useState<NoticeListOut | null>(null);
  const [mineLoading, setMineLoading] = useState(true);
  const [mineError, setMineError] = useState("");
  const [mineSkip, setMineSkip] = useState(0);
  const [mineStatusFilter, setMineStatusFilter] = useState<NoticeStatus | "">(
    "",
  );
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<NoticeOut | null>(null);
  const [viewingMine, setViewingMine] = useState<NoticeOut | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const limit = 12;

  const fetchReceived = useCallback(async () => {
    setReceivedLoading(true);
    setReceivedError("");
    try {
      const params = new URLSearchParams({
        skip: String(receivedSkip),
        limit: String(limit),
        status: "PUBLISHED",
      });

      if (!isAdmin) {
        params.set("exclude_self", "true");
      }

      const result = await apiFetch<NoticeListOut>(`/notices/?${params}`);
      setReceived(result);
    } catch (e: any) {
      setReceivedError(e.message);
    } finally {
      setReceivedLoading(false);
    }
  }, [receivedSkip, isAdmin]);

  const fetchMine = useCallback(async () => {
    setMineLoading(true);
    setMineError("");
    try {
      const params = new URLSearchParams({
        skip: String(mineSkip),
        limit: String(limit),
      });
      if (mineStatusFilter) params.set("status", mineStatusFilter);
      params.set("created_by_self", "true");
      const result = await apiFetch<NoticeListOut>(`/notices/?${params}`);
      setMine(result);
    } catch (e: any) {
      setMineError(e.message);
    } finally {
      setMineLoading(false);
    }
  }, [mineSkip, mineStatusFilter]);

  useEffect(() => {
    fetchReceived();
  }, [fetchReceived]);
  useEffect(() => {
    fetchMine();
  }, [fetchMine]);

  async function handleMarkRead(id: number) {
    try {
      await apiFetch(`/notices/${id}/read`, { method: "POST" });
      setReceived((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          items: prev.items.map((n) =>
            n.id === id ? { ...n, is_read: true } : n,
          ),
          unread_count: Math.max(0, prev.unread_count - 1),
        };
      });
      setViewingReceived((prev) => (prev ? { ...prev, is_read: true } : null));
    } catch (e: any) {
      console.error("Failed to mark as read:", e.message);
    }
  }

  async function handleDelete(id: number) {
    try {
      await apiFetch(`/notices/${id}`, { method: "DELETE" });
      setDeletingId(null);
      fetchMine();
    } catch (e: any) {
      alert(e.message);
    }
  }

  const receivedPages = received ? Math.ceil(received.total / limit) : 0;
  const receivedPage = Math.floor(receivedSkip / limit) + 1;
  const minePages = mine ? Math.ceil(mine.total / limit) : 0;
  const minePage = Math.floor(mineSkip / limit) + 1;

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Notice Board</h1>
            {received && received.unread_count > 0 && (
              <p className="text-sm text-slate-500 mt-0.5">
                <span className="font-semibold text-blue-600">
                  {received.unread_count} unread
                </span>{" "}
                {received.unread_count === 1 ? "notice" : "notices"}
              </p>
            )}
          </div>
          {activeTab === "mine" && (
            <button
              onClick={() => setCreating(true)}
              className="flex items-center gap-2 px-4 py-2.5 bg-slate-900 text-white text-sm font-medium rounded-xl hover:bg-slate-700 transition-colors"
            >
              + New Notice
            </button>
          )}
        </div>

        <div className="flex gap-1 bg-slate-100 rounded-xl p-1 w-fit">
          {(
            [
              ["received", "Received"],
              ["mine", "My Notices"],
            ] as [Tab, string][]
          ).map(([tab, label]) => (
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
              {tab === "received" && received && received.unread_count > 0 && (
                <span className="ml-2 bg-blue-500 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full">
                  {received.unread_count}
                </span>
              )}
            </button>
          ))}
        </div>

        {activeTab === "received" && (
          <div className="space-y-4">
            {receivedLoading && (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                {Array.from({ length: 6 }).map((_, i) => (
                  <div
                    key={i}
                    className="h-52 bg-white rounded-2xl border border-slate-200 animate-pulse"
                  />
                ))}
              </div>
            )}

            {receivedError && (
              <div className="text-center py-20">
                <p className="text-red-600 text-sm font-medium mb-3">
                  {receivedError}
                </p>
                <button
                  onClick={fetchReceived}
                  className="text-sm text-blue-600 underline"
                >
                  Try again
                </button>
              </div>
            )}

            {!receivedLoading && !receivedError && received && (
              <>
                {received.items.length === 0 ? (
                  <div className="text-center py-24">
                    <p className="text-slate-600 text-lg font-medium mb-2">
                      No notices yet
                    </p>
                    <p className="text-slate-400 text-sm">
                      Check back later for updates from the school
                    </p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                    {received.items.map((notice) => (
                      <ReceivedCard
                        key={notice.id}
                        notice={notice}
                        onView={setViewingReceived}
                      />
                    ))}
                  </div>
                )}
                {receivedPages > 1 && (
                  <div className="flex items-center justify-center gap-3 mt-6">
                    <button
                      onClick={() =>
                        setReceivedSkip((s) => Math.max(0, s - limit))
                      }
                      disabled={receivedSkip === 0}
                      className="px-4 py-2 text-sm border border-slate-200 rounded-xl disabled:opacity-40 hover:bg-slate-50 transition-colors bg-white font-medium"
                    >
                      Previous
                    </button>
                    <span className="text-sm text-slate-600 font-medium">
                      Page {receivedPage} of {receivedPages}
                    </span>
                    <button
                      onClick={() => setReceivedSkip((s) => s + limit)}
                      disabled={receivedSkip + limit >= (received?.total ?? 0)}
                      className="px-4 py-2 text-sm border border-slate-200 rounded-xl disabled:opacity-40 hover:bg-slate-50 transition-colors bg-white font-medium"
                    >
                      Next
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {activeTab === "mine" && (
          <div className="space-y-4">
            <div className="flex gap-1.5 flex-wrap">
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
                    setMineStatusFilter(val as NoticeStatus | "");
                    setMineSkip(0);
                  }}
                  className={`text-xs px-3 py-1.5 rounded-full border transition-all ${
                    mineStatusFilter === val
                      ? "bg-slate-900 text-white border-slate-900"
                      : "border-slate-200 text-slate-600 hover:border-slate-400 bg-white"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>

            {mineLoading && (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {Array.from({ length: 6 }).map((_, i) => (
                  <div
                    key={i}
                    className="h-44 bg-white rounded-2xl border border-slate-100 animate-pulse"
                  />
                ))}
              </div>
            )}

            {mineError && (
              <div className="text-center py-16">
                <p className="text-red-600 text-sm mb-3">{mineError}</p>
                <button
                  onClick={fetchMine}
                  className="text-sm text-slate-500 underline"
                >
                  Retry
                </button>
              </div>
            )}

            {!mineLoading && !mineError && mine && (
              <>
                {mine.items.length === 0 ? (
                  <div className="text-center py-24">
                    <p className="text-slate-600 text-lg font-medium mb-2">
                      No notices yet
                    </p>
                    <button
                      onClick={() => setCreating(true)}
                      className="mt-2 text-sm text-slate-700 underline"
                    >
                      Create your first notice
                    </button>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                    {mine.items.map((notice) => (
                      <MyNoticeCard
                        key={notice.id}
                        notice={notice}
                        onEdit={setEditing}
                        onDelete={setDeletingId}
                        onView={setViewingMine}
                      />
                    ))}
                  </div>
                )}
                {minePages > 1 && (
                  <div className="flex items-center justify-center gap-2 mt-8">
                    <button
                      onClick={() => setMineSkip((s) => Math.max(0, s - limit))}
                      disabled={mineSkip === 0}
                      className="px-3 py-1.5 text-sm border border-slate-200 rounded-lg disabled:opacity-40 hover:bg-slate-50 transition-colors"
                    >
                      Previous
                    </button>
                    <span className="text-sm text-slate-500">
                      Page {minePage} of {minePages}
                    </span>
                    <button
                      onClick={() => setMineSkip((s) => s + limit)}
                      disabled={mineSkip + limit >= (mine?.total ?? 0)}
                      className="px-3 py-1.5 text-sm border border-slate-200 rounded-lg disabled:opacity-40 hover:bg-slate-50 transition-colors"
                    >
                      Next
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>

      {viewingReceived && (
        <ReceivedViewModal
          notice={viewingReceived}
          onClose={() => setViewingReceived(null)}
          onMarkRead={handleMarkRead}
        />
      )}

      {viewingMine && (
        <MyNoticeViewModal
          notice={viewingMine}
          onClose={() => setViewingMine(null)}
        />
      )}

      {creating && (
        <Modal title="New Notice" onClose={() => setCreating(false)}>
          <NoticeForm
            onClose={() => setCreating(false)}
            onSave={() => {
              setCreating(false);
              fetchMine();
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
              fetchMine();
            }}
          />
        </Modal>
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

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Bot,
  ChevronLeft,
  Clock,
  History,
  Loader2,
  MessageCircle,
  Plus,
  RefreshCw,
  Send,
  Mail,
  Trash2,
  X,
  Globe,
  Sparkles,
  SlidersHorizontal,
  Languages,
} from "lucide-react";
import {
  createChatSession,
  getChatMessages,
  getChatSessions,
  sendChatAnswerEmail,
  sendChatAnswerTelegram,
  streamLessonChatMessage,
} from "@/lib/chatApi";
import { apiFetch } from "@/lib/api";
import type { ChatMessage, ChatSession, LMSLesson } from "@/types";
import ReactMarkdown from "react-markdown";

// Language support
const SUPPORTED_LANGUAGES = [
  { code: "en", label: "English" },
  { code: "hi", label: "Hindi" },
  { code: "es", label: "Spanish" },
  { code: "fr", label: "French" },
  { code: "de", label: "German" },
  { code: "ar", label: "Arabic" },
  { code: "zh", label: "Chinese" },
  { code: "ja", label: "Japanese" },
  { code: "pt", label: "Portuguese" },
  { code: "ur", label: "Urdu" },
  { code: "bn", label: "Bengali" },
  { code: "te", label: "Telugu" },
  { code: "mr", label: "Marathi" },
  { code: "ta", label: "Tamil" },
  { code: "gu", label: "Gujarati" },
  { code: "kn", label: "Kannada" },
  { code: "ml", label: "Malayalam" },
  { code: "pa", label: "Punjabi" },
] as const;

/* ─── Types ─── */
type LocalMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at?: string | null;
  isEnhanced?: boolean;
  suggestions?: string[];
};

type ShareChannel = "email" | "telegram";

type ShareDraft = {
  channel: ShareChannel;
  messageId: string;
  content: string;
  email: string;
  subject: string;
  telegramChatId: string;
};

type Props = {
  lesson: LMSLesson;
  courseTitle?: string;
  embedded?: boolean;
};

/* ─── Helpers ─── */
function storageKey(lessonId: number) {
  return `erp_lms_lesson_chat_session_${lessonId}`;
}

function normalizeMessages(rows: ChatMessage[]): LocalMessage[] {
  return rows
    .filter((r) => r.role === "user" || r.role === "assistant")
    .map(
      (r): LocalMessage => ({
        id: String(r.id),
        role: r.role === "assistant" ? "assistant" : "user",
        content: r.content || "",
        created_at: r.created_at ?? null,
        isEnhanced: r.is_enhanced ?? false,
      }),
    )
    .filter((r) => r.content.trim().length > 0);
}

function formatSessionTime(iso?: string | null): string {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);
    if (diffMins < 1) return "just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  } catch {
    return "";
  }
}

function SessionTitle({ session }: { session: ChatSession }) {
  const title =
    session.title && session.title !== "New Chat"
      ? session.title
      : "New conversation";
  return <>{title}</>;
}

/* ─── Main component ─── */
export default function CourseLessonChat({
  lesson,
  courseTitle,
  embedded = false,
}: Props) {
  const [open, setOpen] = useState(embedded);
  const [view, setView] = useState<"chat" | "history">("chat");

  /* Chat state */
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<LocalMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  const [webSearch, setWebSearch] = useState(false);
  const [enhancePrompt, setEnhancePrompt] = useState(false);

  const [language, setLanguage] = useState(lesson.language || "en");

  /* Session history state */
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [loadingSessions, setLoadingSessions] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [loadingSession, setLoadingSession] = useState<string | null>(null);

  const bottomRef = useRef<HTMLDivElement | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);

  /* ── Auto-scroll ── */
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, sending]);

  /* ── Load current session messages on mount/lesson change ── */
  useEffect(() => {
    setMessages([]);
    setSessionId(null);
    setQuestion("");
    setError("");
    setView("chat");
  }, [lesson.id]);

  useEffect(() => {
    if (!open || typeof window === "undefined") return;
    const saved = localStorage.getItem(storageKey(lesson.id));
    if (!saved || saved === sessionId) return;
    setLoadingHistory(true);
    setSessionId(saved);
    getChatMessages(saved)
      .then((rows) => setMessages(normalizeMessages(rows)))
      .catch(() => {
        localStorage.removeItem(storageKey(lesson.id));
        setSessionId(null);
        setMessages([]);
      })
      .finally(() => setLoadingHistory(false));
  }, [lesson.id, open, sessionId]);

  /* ── Load sessions for history panel ── */
  const loadSessions = useCallback(async () => {
    setLoadingSessions(true);
    try {
      const rows = await getChatSessions();
      setSessions(rows);
    } catch {
      /* silently ignore */
    } finally {
      setLoadingSessions(false);
    }
  }, []);

  const openHistory = () => {
    setView("history");
    loadSessions();
  };

  /* ── Session actions ── */
  const resetChat = () => {
    if (typeof window !== "undefined")
      localStorage.removeItem(storageKey(lesson.id));
    setSessionId(null);
    setMessages([]);
    setQuestion("");
    setError("");
  };

  const ensureSession = async () => {
    if (sessionId) return sessionId;
    const session = await createChatSession();
    setSessionId(session.id);
    if (typeof window !== "undefined")
      localStorage.setItem(storageKey(lesson.id), session.id);
    return session.id;
  };

  const loadSessionMessages = async (sid: string) => {
    setLoadingSession(sid);
    try {
      const rows = await getChatMessages(sid);
      const normalized = normalizeMessages(rows);
      setSessionId(sid);
      setMessages(normalized);
      if (typeof window !== "undefined")
        localStorage.setItem(storageKey(lesson.id), sid);
      setView("chat");
    } catch {
      setError("Failed to load session.");
    } finally {
      setLoadingSession(null);
    }
  };

  const deleteSession = async (sid: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setDeletingId(sid);
    try {
      await apiFetch(`/sessions/${sid}`, { method: "DELETE" });
      setSessions((prev) => prev.filter((s) => s.id !== sid));
      if (sid === sessionId) {
        resetChat();
        setView("chat");
      }
    } catch {
      /* silently ignore */
    } finally {
      setDeletingId(null);
    }
  };

  const cancelStream = () => {
    abortControllerRef.current?.abort();
    setSending(false);
    setMessages((prev) => {
      const last = prev[prev.length - 1];
      if (last?.role === "assistant" && !last.content.trim()) {
        return prev.slice(0, -1); // remove empty assistant bubble
      }
      return prev;
    });
  };

  /* ── Send message ── */
  const submitQuestion = async () => {
    const clean = question.trim();
    if (!clean || sending) return;
    setSending(true);
    setError("");
    setQuestion("");

    const userId = `user-${Date.now()}`;

    const userMsg: LocalMessage = {
      id: userId,
      role: "user",
      content: clean,
    };

    const assistantId = `assistant-${Date.now()}`;

    const assistantMsg: LocalMessage = {
      id: assistantId,
      role: "assistant",
      content: "",
    };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    try {
      const sid = await ensureSession();
      let answer = "";
      abortControllerRef.current = new AbortController();
      await streamLessonChatMessage({
        sessionId: sid,
        content: clean,
        lessonId: lesson.id,
        language: language,
        webSearch: webSearch,
        enhancePrompt: enhancePrompt,
        signal: abortControllerRef.current.signal,
        callbacks: {
          onEnhancedPrompt: (enhanced) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === userId
                  ? { ...m, content: enhanced, isEnhanced: true }
                  : m,
              ),
            );
          },
          onSuggestedQuestions: (suggestions) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId ? { ...m, suggestions } : m,
              ),
            );
          },
          onToken: (token) => {
            answer += token;
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId ? { ...m, content: answer } : m,
              ),
            );
          },
        },
      });
      if (!answer.trim()) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? {
                  ...m,
                  content: "I could not generate a response. Please try again.",
                }
              : m,
          ),
        );
      }
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") {
        return;
      }
      setError(err instanceof Error ? err.message : "Failed to send question");
      setMessages((prev) => prev.filter((m) => m.id !== assistantId));
    } finally {
      abortControllerRef.current = null;
      setSending(false);
    }
  };

  /* ── Render ── */
  const inner = (
    <ChatInner
      view={view}
      setView={setView}
      messages={messages}
      sessions={sessions}
      sessionId={sessionId}
      loadingHistory={loadingHistory}
      loadingSessions={loadingSessions}
      loadingSession={loadingSession}
      deletingId={deletingId}
      sending={sending}
      error={error}
      question={question}
      setQuestion={setQuestion}
      submitQuestion={submitQuestion}
      resetChat={resetChat}
      openHistory={openHistory}
      loadSessionMessages={loadSessionMessages}
      deleteSession={deleteSession}
      lesson={lesson}
      courseTitle={courseTitle}
      bottomRef={bottomRef}
      embedded={embedded}
      cancelStream={cancelStream}
      webSearch={webSearch}
      setWebSearch={setWebSearch}
      enhancePrompt={enhancePrompt}
      setEnhancePrompt={setEnhancePrompt}
      language={language}
      setLanguage={setLanguage}
    />
  );

  if (!embedded) {
    return (
      <div
        style={{
          borderRadius: 14,
          border: "1px solid #e2e8f0",
          background: "#f8fafc",
          marginTop: 12,
          overflow: "hidden",
        }}
      >
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          style={{
            display: "flex",
            width: "100%",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 10,
            padding: "10px 14px",
            background: "none",
            border: "none",
            cursor: "pointer",
          }}
        >
          <span
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              fontSize: "0.8125rem",
              fontWeight: 600,
              color: "#0f172a",
            }}
          >
            <span
              style={{
                borderRadius: 8,
                background: "#0f172a",
                padding: "5px 6px",
                display: "flex",
                alignItems: "center",
              }}
            >
              <Bot size={14} color="white" />
            </span>
            Ask AI about this lesson
          </span>
          <span style={{ color: "#94a3b8" }}>
            {open ? (
              <X size={16} />
            ) : (
              <span style={{ fontSize: "0.75rem" }}>Open</span>
            )}
          </span>
        </button>
        {open && <div style={{ borderTop: "1px solid #e2e8f0" }}>{inner}</div>}
      </div>
    );
  }

  return inner;
}

/* ─── Inner shell — handles view switching ─── */
type InnerProps = {
  view: "chat" | "history";
  setView: (v: "chat" | "history") => void;
  messages: LocalMessage[];
  sessions: ChatSession[];
  sessionId: string | null;
  loadingHistory: boolean;
  loadingSessions: boolean;
  loadingSession: string | null;
  deletingId: string | null;
  sending: boolean;
  error: string;
  question: string;
  setQuestion: (v: string) => void;
  submitQuestion: () => void;
  resetChat: () => void;
  openHistory: () => void;
  cancelStream: () => void;
  loadSessionMessages: (sid: string) => void;
  deleteSession: (sid: string, e: React.MouseEvent) => void;
  lesson: LMSLesson;
  courseTitle?: string;
  bottomRef: React.RefObject<HTMLDivElement | null>;
  embedded: boolean;
  webSearch: boolean;
  setWebSearch: (v: boolean) => void;
  enhancePrompt: boolean;
  setEnhancePrompt: (v: boolean) => void;
  language: string;
  setLanguage: (v: string) => void;
};

function ChatInner({
  view,
  setView,
  messages,
  sessions,
  sessionId,
  loadingHistory,
  loadingSessions,
  loadingSession,
  deletingId,
  sending,
  error,
  question,
  setQuestion,
  submitQuestion,
  resetChat,
  openHistory,
  loadSessionMessages,
  deleteSession,
  lesson,
  courseTitle,
  bottomRef,
  embedded,
  cancelStream,
  webSearch,
  setWebSearch,
  enhancePrompt,
  setEnhancePrompt,
  language,
  setLanguage,
}: InnerProps) {
  const [optsOpen, setOptsOpen] = useState(false);
  const [shareDraft, setShareDraft] = useState<ShareDraft | null>(null);
  const [shareSending, setShareSending] = useState(false);
  const [shareError, setShareError] = useState("");
  const [shareNotice, setShareNotice] = useState("");
  const inputRef = useRef<HTMLTextAreaElement | null>(null);

  const openShareTool = (channel: ShareChannel, msg: LocalMessage) => {
    const defaultSubject = lesson.title
      ? `AI Tutor response - ${lesson.title}`
      : "AI Tutor response";

    setShareDraft({
      channel,
      messageId: msg.id,
      content: msg.content,
      email: "",
      subject: defaultSubject,
      telegramChatId: "",
    });
    setShareError("");
    setShareNotice("");
  };

  const updateShareDraft = (patch: Partial<ShareDraft>) => {
    setShareDraft((prev) => (prev ? { ...prev, ...patch } : prev));
  };

  const findLastAssistantMessage = () =>
    [...messages]
      .reverse()
      .find((msg) => msg.role === "assistant" && msg.content.trim());

  const latestAssistantId = findLastAssistantMessage()?.id ?? null;

  const fillInputWithSuggestion = (suggestion: string) => {
    setQuestion(suggestion);
    requestAnimationFrame(() => inputRef.current?.focus());
  };

  const openShareToolFromCommand = (): boolean => {
    const clean = question.trim();
    const wantsSend = /(send|share|forward|bhej|भेज)/i.test(clean);
    const wantsEmail = /(email|mail)/i.test(clean);
    const wantsTelegram = /telegram/i.test(clean);

    if (!wantsSend || (!wantsEmail && !wantsTelegram)) return false;

    const lastAssistant = findLastAssistantMessage();
    if (!lastAssistant) {
      setShareNotice("No AI response is available to send yet.");
      setQuestion("");
      return true;
    }

    const emailMatch = clean.match(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i);
    const chatMatch = clean.match(
      /(?:chat\s*id|chat_id|telegram)\s*[:=\-]?\s*(-?\d{5,}|@[A-Za-z0-9_]{5,})/i,
    );

    openShareTool(wantsTelegram ? "telegram" : "email", lastAssistant);
    setShareDraft((prev) =>
      prev
        ? {
            ...prev,
            email: emailMatch?.[0] || prev.email,
            telegramChatId: chatMatch?.[1] || prev.telegramChatId,
          }
        : prev,
    );
    setQuestion("");
    return true;
  };

  const handleSubmitFromInput = () => {
    if (openShareToolFromCommand()) return;
    submitQuestion();
  };

  const submitShareTool = async () => {
    if (!shareDraft || shareSending) return;
    setShareSending(true);
    setShareError("");
    setShareNotice("");

    try {
      const response =
        shareDraft.channel === "email"
          ? await sendChatAnswerEmail({
              content: shareDraft.content,
              toEmail: shareDraft.email.trim() || undefined,
              subject: shareDraft.subject.trim() || undefined,
              lessonTitle: lesson.title,
              courseTitle,
            })
          : await sendChatAnswerTelegram({
              content: shareDraft.content,
              chatId: shareDraft.telegramChatId.trim() || undefined,
              lessonTitle: lesson.title,
              courseTitle,
            });

      setShareNotice(response.message || "AI response sent successfully.");
      setShareDraft(null);
    } catch (err) {
      setShareError(err instanceof Error ? err.message : "Failed to send AI response");
    } finally {
      setShareSending(false);
    }
  };

  return (
    <>
      <style>{`
        .clc-root {
          display: flex; flex-direction: column;
          flex: 1; min-height: 0;
          font-family: 'Segoe UI', system-ui, sans-serif;
        }
        .clc-root * { box-sizing: border-box; }

        /* ── Header ── */
        .clc-header {
          display: flex; align-items: center; gap: 8px;
          padding: 10px 12px 8px; flex-shrink: 0;
          border-bottom: 1px solid #e2e8f0;
          background: #fafafa;
        }
        .clc-icon-btn {
          display: flex; align-items: center; justify-content: center;
          width: 28px; height: 28px; border-radius: 8px;
          border: 1px solid #e2e8f0; background: white;
          cursor: pointer; color: #64748b; flex-shrink: 0;
          transition: background 0.12s, color 0.12s;
        }
        .clc-icon-btn:hover { background: #f1f5f9; color: #0f172a; }
        .clc-icon-btn.active { background: #ede9fe; color: #7c3aed; border-color: #c4b5fd; }
        .clc-title { flex: 1; min-width: 0; }
        .clc-title p { margin: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

        /* ── Chat messages area ── */
        .clc-messages {
          flex: 1; min-height: 0; overflow-y: auto;
          padding: 10px; display: flex; flex-direction: column; gap: 8px;
          background: white;
          scrollbar-width: thin; scrollbar-color: #cbd5e1 transparent;
        }
        .clc-messages::-webkit-scrollbar { width: 4px; }
        .clc-messages::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 99px; }

        /* Message bubbles */
        .clc-bubble-wrap { display: flex; }
        .clc-bubble-wrap.user { justify-content: flex-end; }
        .clc-bubble-wrap.assistant { justify-content: flex-start; }
        .clc-bubble {
          max-width: 88%; padding: 8px 11px;
          font-size: 0.78rem; line-height: 1.6; white-space: pre-wrap;
        }
        .clc-bubble.user {
          background: #0f172a; color: white;
          border-radius: 14px 14px 3px 14px;
        }
        .clc-bubble.assistant {
          background: #f1f5f9; color: #1e293b;
          border-radius: 14px 14px 14px 3px;
          border: 1px solid #e8edf5;
        }
        .clc-typing {
          display: flex; align-items: center; gap: 4px; padding: 4px 2px;
        }
        .clc-dot {
          width: 6px; height: 6px; border-radius: 50%;
          background: #94a3b8; animation: clcBounce 1.2s ease-in-out infinite;
        }
        .clc-dot:nth-child(2) { animation-delay: 0.2s; }
        .clc-dot:nth-child(3) { animation-delay: 0.4s; }
        @keyframes clcBounce {
          0%, 60%, 100% { transform: translateY(0); opacity: 0.5; }
          30% { transform: translateY(-5px); opacity: 1; }
        }
        .clc-ai-badge {
          display: flex; align-items: center; gap: 5px;
          font-size: 0.65rem; font-weight: 700; color: #7c3aed;
          margin-bottom: 3px; text-transform: uppercase; letter-spacing: 0.05em;
        }
        .clc-share-actions {
          display: flex; align-items: center; gap: 6px; margin-top: 8px;
          padding-top: 7px; border-top: 1px solid #e2e8f0;
        }
        .clc-share-btn {
          border: 1px solid #e2e8f0; background: white; color: #475569;
          border-radius: 999px; padding: 4px 8px; font-size: 0.68rem;
          font-weight: 700; display: inline-flex; align-items: center; gap: 4px;
          cursor: pointer; transition: background 0.12s, color 0.12s;
        }
        .clc-share-btn:hover { background: #ede9fe; color: #6d28d9; border-color: #c4b5fd; }
        .clc-share-notice {
          margin: 8px 10px 0; padding: 8px 10px; border-radius: 10px;
          background: #ecfdf5; color: #047857; border: 1px solid #bbf7d0;
          font-size: 0.74rem; font-weight: 600;
        }
        .clc-share-panel {
          margin: 0 10px 8px; padding: 10px; border-radius: 12px;
          border: 1px solid #ddd6fe; background: #faf5ff;
          display: flex; flex-direction: column; gap: 8px; flex-shrink: 0;
        }
        .clc-share-panel-title {
          display: flex; align-items: center; gap: 6px;
          font-size: 0.76rem; font-weight: 800; color: #4c1d95;
        }
        .clc-share-field {
          width: 100%; border: 1px solid #d8b4fe; border-radius: 9px;
          padding: 7px 9px; font-size: 0.76rem; outline: none; background: white;
        }
        .clc-share-help { font-size: 0.68rem; color: #7c3aed; margin: -3px 0 0; }
        .clc-share-error {
          font-size: 0.7rem; color: #b91c1c; background: #fee2e2;
          border: 1px solid #fecaca; padding: 6px 8px; border-radius: 8px;
        }
        .clc-share-actions-row { display: flex; justify-content: flex-end; gap: 7px; }
        .clc-share-cancel, .clc-share-send {
          border: none; border-radius: 9px; padding: 7px 11px; font-size: 0.72rem;
          font-weight: 800; cursor: pointer; display: inline-flex; align-items: center; gap: 5px;
        }
        .clc-share-cancel { background: white; color: #64748b; border: 1px solid #e2e8f0; }
        .clc-share-send { background: #7c3aed; color: white; }
        .clc-share-send:disabled { background: #c4b5fd; cursor: not-allowed; }

        /* ── Input bar ── */
        .clc-input-bar {
          display: flex; gap: 6px; padding: 8px 10px; flex-shrink: 0;
          border-top: 1px solid #e2e8f0; background: #fafafa;
          align-items: flex-end; position: relative;
        }
        .clc-textarea {
          flex: 1; resize: none; border: 1px solid #e2e8f0; border-radius: 10px;
          padding: 8px 10px; font-size: 0.78rem; outline: none; font-family: inherit;
          transition: border-color 0.13s; line-height: 1.5; background: white;
          min-height: 36px; max-height: 100px; overflow-y: auto;
        }
        .clc-textarea:focus { border-color: #a78bfa; }
        .clc-send-btn {
          width: 36px; height: 36px; border-radius: 10px; border: none; flex-shrink: 0;
          display: flex; align-items: center; justify-content: center;
          transition: background 0.13s; cursor: pointer;
        }
        .clc-send-btn:disabled { cursor: not-allowed; }

        /* ── Options dropdown ── */
        .clc-opts-btn {
          width: 36px; height: 36px; border-radius: 10px; flex-shrink: 0;
          border: 1px solid #e2e8f0; background: white; cursor: pointer;
          display: flex; align-items: center; justify-content: center;
          color: #64748b; transition: all 0.12s; position: relative;
        }
        .clc-opts-btn:hover { background: #f1f5f9; color: #0f172a; }
        .clc-opts-btn.open { background: #ede9fe; border-color: #c4b5fd; color: #7c3aed; }
        .clc-dropdown {
          position: absolute; bottom: calc(100% + 6px); right: 10px;
          background: white; border: 1px solid #e2e8f0; border-radius: 12px;
          padding: 6px; display: flex; flex-direction: column; gap: 2px;
          box-shadow: 0 4px 16px rgba(0,0,0,0.08); z-index: 50; min-width: 160px;
        }
        .clc-dropdown-item {
          display: flex; align-items: center; justify-content: space-between;
          gap: 8px; padding: 7px 10px; border-radius: 8px;
          border: none; background: none; cursor: pointer;
          font-size: 0.75rem; font-weight: 600; color: #374151;
          transition: background 0.1s;
          width: 100%; text-align: left;
        }
        .clc-dropdown-item:hover { background: #f8fafc; }
        .clc-dropdown-item.active { color: #7c3aed; }
        .clc-toggle-pill {
          width: 28px; height: 16px; border-radius: 99px; flex-shrink: 0;
          transition: background 0.15s; position: relative;
          background: #e2e8f0;
        }
        .clc-toggle-pill.on { background: #7c3aed; }
        .clc-toggle-pill::after {
          content: ''; position: absolute; top: 2px; left: 2px;
          width: 12px; height: 12px; border-radius: 50%; background: white;
          transition: transform 0.15s;
        }
        .clc-toggle-pill.on::after { transform: translateX(12px); }
        .clc-dropdown-label {
          display: flex; align-items: center; gap: 6px;
        }

        .clc-enhanced-badge {
          display: inline-flex; align-items: center; gap: 3px;
          font-size: 0.6rem; font-weight: 700; letter-spacing: 0.04em;
          color: #a855f7; background: #faf5ff;
          border: 1px solid #e9d5ff; border-radius: 6px;
          padding: 3px 6px; margin-bottom: 5px;
          text-transform: uppercase;
        }

        .clc-suggestions {
          margin-top: 8px; padding-top: 8px; border-top: 1px solid #e2e8f0;
          display: flex; flex-direction: column; gap: 6px;
        }
        .clc-suggestions-title {
          display: flex; align-items: center; gap: 5px;
          color: #7c3aed; font-size: 0.66rem; font-weight: 800;
          text-transform: uppercase; letter-spacing: 0.04em;
        }
        .clc-suggestion-btn {
          width: 100%; text-align: left; border: 1px solid #ddd6fe;
          background: #ffffff; color: #334155; border-radius: 10px;
          padding: 7px 9px; font-size: 0.72rem; line-height: 1.35;
          cursor: pointer; transition: background 0.12s, border-color 0.12s, color 0.12s;
        }
        .clc-suggestion-btn:hover {
          background: #f5f3ff; border-color: #a78bfa; color: #5b21b6;
        }

        /* ── History panel ── */
        .clc-history {
          flex: 1; min-height: 0; display: flex; flex-direction: column;
        }
        .clc-hist-scroll {
          flex: 1; min-height: 0; overflow-y: auto; padding: 8px;
          scrollbar-width: thin; scrollbar-color: #cbd5e1 transparent;
        }
        .clc-hist-scroll::-webkit-scrollbar { width: 4px; }
        .clc-hist-scroll::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 99px; }
        .clc-session-item {
          width: 100%; text-align: left; background: none;
          border: 1px solid #e2e8f0; border-radius: 10px;
          padding: 10px 12px; cursor: pointer; margin-bottom: 6px;
          transition: border-color 0.12s, background 0.12s;
          display: flex; align-items: flex-start; gap: 10px;
          position: relative;
        }
        .clc-session-item:hover { background: #f8fafc; border-color: #c4b5fd; }
        .clc-session-item.current { background: #ede9fe; border-color: #7c3aed; }
        .clc-session-icon {
          width: 30px; height: 30px; border-radius: 8px; flex-shrink: 0;
          display: flex; align-items: center; justify-content: center;
          background: #f1f5f9;
        }
        .clc-session-item.current .clc-session-icon { background: #7c3aed; }
        .clc-session-del {
          position: absolute; top: 8px; right: 8px;
          width: 22px; height: 22px; border-radius: 6px;
          border: none; background: none; cursor: pointer;
          display: flex; align-items: center; justify-content: center;
          color: #94a3b8; opacity: 0; transition: opacity 0.13s, background 0.13s;
        }
        .clc-session-item:hover .clc-session-del { opacity: 1; }
        .clc-session-del:hover { background: #fee2e2; color: #dc2626; }

        /* ── Empty state ── */
        .clc-empty {
          display: flex; flex-direction: column; align-items: center;
          justify-content: center; gap: 8px; padding: 24px;
          text-align: center; flex: 1;
        }

        /* ── Error banner ── */
        .clc-error {
          margin: 6px 10px; padding: 7px 10px;
          background: #fee2e2; border-radius: 8px;
          font-size: 0.73rem; color: #991b1b;
          flex-shrink: 0;
        }

        /* ── Hint pill ── */
        .clc-hint {
          padding: 10px 12px; background: #eff6ff;
          border-radius: 10px; font-size: 0.75rem; color: #1d4ed8; line-height: 1.55;
        }

        /* spin util */
        .clc-spin { animation: clcSpin 0.7s linear infinite; }
        @keyframes clcSpin { to { transform: rotate(360deg); } }


        /* markdown */
        .clc-md { font-size: 0.78rem; line-height: 1.6; color: #1e293b; }
        .clc-md p { margin: 0 0 6px; }
        .clc-md p:last-child { margin-bottom: 0; }
        .clc-md strong { font-weight: 700; }
        .clc-md em { font-style: italic; }
        .clc-md ul, .clc-md ol { margin: 4px 0 6px; padding-left: 16px; }
        .clc-md li { margin-bottom: 2px; }
        .clc-md code {
          background: #f1f5f9; border: 1px solid #e2e8f0;
          border-radius: 4px; padding: 1px 5px;
          font-size: 0.73rem; font-family: monospace;
        }
        .clc-md pre {
          background: #0f172a; border-radius: 8px;
          padding: 10px 12px; overflow-x: auto; margin: 6px 0;
        }
        .clc-md pre code {
          background: none; border: none; padding: 0;
          color: #e2e8f0; font-size: 0.72rem;
        }
        .clc-md h1, .clc-md h2, .clc-md h3 {
          font-weight: 700; margin: 8px 0 4px; color: #0f172a;
        }
        .clc-md h1 { font-size: 0.9rem; }
        .clc-md h2 { font-size: 0.85rem; }
        .clc-md h3 { font-size: 0.8rem; }
        .clc-md a { color: #7c3aed; text-decoration: underline; }
        .clc-md blockquote {
          border-left: 3px solid #c4b5fd; margin: 6px 0;
          padding: 2px 10px; color: #64748b;
        }
      `}</style>

      <div className="clc-root">
        {/* ── Header ── */}
        <div className="clc-header">
          {view === "history" ? (
            <button
              type="button"
              className="clc-icon-btn"
              onClick={() => setView("chat")}
              title="Back to chat"
            >
              <ChevronLeft size={15} />
            </button>
          ) : (
            <div
              style={{
                width: 28,
                height: 28,
                borderRadius: 8,
                background: "#7c3aed",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
              }}
            >
              <Bot size={14} color="white" />
            </div>
          )}

          <div className="clc-title">
            {view === "history" ? (
              <>
                <p
                  style={{
                    fontSize: "0.78rem",
                    fontWeight: 700,
                    color: "#0f172a",
                  }}
                >
                  Chat History
                </p>
                <p style={{ fontSize: "0.65rem", color: "#94a3b8" }}>
                  {lesson.title}
                </p>
              </>
            ) : (
              <>
                <p
                  style={{
                    fontSize: "0.78rem",
                    fontWeight: 700,
                    color: "#0f172a",
                  }}
                >
                  AI Tutor
                </p>
                <p
                  style={{
                    fontSize: "0.65rem",
                    color: "#94a3b8",
                    maxWidth: 160,
                  }}
                >
                  {courseTitle ? `${courseTitle} · ` : ""}
                  {lesson.title}
                </p>
              </>
            )}
          </div>

          {view === "chat" && (
            <>
              <button
                type="button"
                className="clc-icon-btn"
                onClick={openHistory}
                title="Chat history"
              >
                <History size={14} />
              </button>
              <button
                type="button"
                className="clc-icon-btn"
                onClick={resetChat}
                title="New chat"
              >
                <Plus size={14} />
              </button>
            </>
          )}

          {view === "history" && (
            <button
              type="button"
              className="clc-icon-btn"
              onClick={() => {
                setView("chat");
              }}
              title="New chat"
              style={{ marginLeft: "auto" }}
            >
              <Plus size={14} />
            </button>
          )}
        </div>

        {/* ── CHAT VIEW ── */}
        {view === "chat" && (
          <>
            {error && <div className="clc-error">{error}</div>}

            <div className="clc-messages">
              {loadingHistory && (
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    fontSize: "0.75rem",
                    color: "#94a3b8",
                    padding: "4px 0",
                  }}
                >
                  <Loader2 size={13} className="clc-spin" /> Loading messages…
                </div>
              )}

              {!loadingHistory && messages.length === 0 && (
                <div className="clc-hint">
                  <strong style={{ display: "block", marginBottom: 4 }}>
                    Ask anything about this lesson
                  </strong>
                  Try <em>"Explain this simply"</em>,{" "}
                  <em>"Give me an example"</em>, or{" "}
                  <em>"What's the main idea?"</em>
                </div>
              )}

              {messages.map((msg) => (
                <div key={msg.id} className={`clc-bubble-wrap ${msg.role}`}>
                  <div className={`clc-bubble ${msg.role}`}>
                    {msg.role === "assistant" && (
                      <div className="clc-ai-badge">
                        <Bot size={10} /> AI Tutor
                      </div>
                    )}

                    {/* Enhanced prompt badge */}
                    {msg.isEnhanced && (
                      <div
                        style={{
                          display: "flex",
                          flexDirection: "column",
                          alignItems: "flex-start",
                        }}
                      >
                        <div className="clc-enhanced-badge">
                          <Sparkles size={9} />
                          Enhanced
                        </div>
                      </div>
                    )}

                    {msg.content ? (
                      msg.role === "assistant" ? (
                        <div className="clc-md">
                          <ReactMarkdown>{msg.content}</ReactMarkdown>
                        </div>
                      ) : (
                        msg.content
                      )
                    ) : msg.role === "assistant" && sending ? (
                      <div className="clc-typing">
                        <div className="clc-dot" />
                        <div className="clc-dot" />
                        <div className="clc-dot" />
                      </div>
                    ) : null}

                    {msg.role === "assistant" && msg.content.trim() && (
                      <div className="clc-share-actions">
                        <button
                          type="button"
                          className="clc-share-btn"
                          onClick={() => openShareTool("email", msg)}
                          title="Send this AI response to email"
                        >
                          <Mail size={11} /> Email
                        </button>
                        <button
                          type="button"
                          className="clc-share-btn"
                          onClick={() => openShareTool("telegram", msg)}
                          title="Send this AI response to Telegram"
                        >
                          <Send size={11} /> Telegram
                        </button>
                      </div>
                    )}

                    {msg.role === "assistant" &&
                      msg.id === latestAssistantId &&
                      !sending &&
                      msg.suggestions &&
                      msg.suggestions.length > 0 && (
                        <div className="clc-suggestions">
                          <div className="clc-suggestions-title">
                            <Sparkles size={10} /> Suggested questions
                          </div>
                          {msg.suggestions.map((suggestion) => (
                            <button
                              key={suggestion}
                              type="button"
                              className="clc-suggestion-btn"
                              onClick={() => fillInputWithSuggestion(suggestion)}
                            >
                              {suggestion}
                            </button>
                          ))}
                        </div>
                      )}
                  </div>
                </div>
              ))}
              <div ref={bottomRef} />
            </div>

            {shareNotice && <div className="clc-share-notice">{shareNotice}</div>}

            {shareDraft && (
              <div className="clc-share-panel">
                <div className="clc-share-panel-title">
                  {shareDraft.channel === "email" ? (
                    <Mail size={14} />
                  ) : (
                    <Send size={14} />
                  )}
                  Send AI response to {shareDraft.channel === "email" ? "Email" : "Telegram"}
                </div>

                {shareDraft.channel === "email" ? (
                  <>
                    <input
                      className="clc-share-field"
                      type="email"
                      value={shareDraft.email}
                      onChange={(e) => updateShareDraft({ email: e.target.value })}
                      placeholder="Recipient email (blank = current login email)"
                    />
                    <input
                      className="clc-share-field"
                      value={shareDraft.subject}
                      onChange={(e) => updateShareDraft({ subject: e.target.value })}
                      placeholder="Email subject"
                    />
                  </>
                ) : (
                  <>
                    <input
                      className="clc-share-field"
                      value={shareDraft.telegramChatId}
                      onChange={(e) =>
                        updateShareDraft({ telegramChatId: e.target.value })
                      }
                      placeholder="Telegram chat ID (blank = backend default)"
                    />
                    <p className="clc-share-help">
                      Telegram user/group must start your bot first, otherwise Telegram will block the message.
                    </p>
                  </>
                )}

                {shareError && <div className="clc-share-error">{shareError}</div>}

                <div className="clc-share-actions-row">
                  <button
                    type="button"
                    className="clc-share-cancel"
                    onClick={() => setShareDraft(null)}
                    disabled={shareSending}
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    className="clc-share-send"
                    onClick={submitShareTool}
                    disabled={shareSending}
                  >
                    {shareSending && <Loader2 size={12} className="clc-spin" />}
                    Send
                  </button>
                </div>
              </div>
            )}

            {/* <div className="clc-input-bar">
              <textarea
                ref={inputRef}
                className="clc-textarea"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="Ask your doubt…"
                rows={1}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSubmitFromInput();
                  }
                }}
              />
              {sending ? (
                <button
                  type="button"
                  className="clc-send-btn"
                  onClick={cancelStream}
                  style={{ background: "#fee2e2", color: "#dc2626" }}
                >
                  <X size={15} />
                </button>
              ) : (
                <button
                  type="button"
                  className="clc-send-btn"
                  onClick={handleSubmitFromInput}
                  disabled={!question.trim()}
                  style={{
                    background: !question.trim() ? "#f1f5f9" : "#7c3aed",
                    color: !question.trim() ? "#94a3b8" : "white",
                  }}
                >
                  <Send size={15} />
                </button>
              )}
            </div> */}

            <div className="clc-input-bar">
              <textarea
                ref={inputRef}
                className="clc-textarea"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="Ask your doubt…"
                rows={1}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSubmitFromInput();
                  }
                }}
              />

              {/* Options button + dropdown */}
              <div style={{ position: "relative", flexShrink: 0 }}>
                <button
                  type="button"
                  className={`clc-opts-btn${optsOpen ? " open" : ""}`}
                  onClick={() => setOptsOpen((v) => !v)}
                  title="Options"
                >
                  <SlidersHorizontal size={14} />
                </button>

                {optsOpen && (
                  <div className="clc-dropdown">
                    <button
                      type="button"
                      className={`clc-dropdown-item${webSearch ? " active" : ""}`}
                      onClick={() => setWebSearch(!webSearch)}
                    >
                      <span className="clc-dropdown-label">
                        <Globe size={13} /> Web search
                      </span>
                      <span
                        className={`clc-toggle-pill${webSearch ? " on" : ""}`}
                      />
                    </button>
                    <button
                      type="button"
                      className={`clc-dropdown-item${enhancePrompt ? " active" : ""}`}
                      onClick={() => setEnhancePrompt(!enhancePrompt)}
                    >
                      <span className="clc-dropdown-label">
                        <Sparkles size={13} /> Enhance prompt
                      </span>
                      <span
                        className={`clc-toggle-pill${enhancePrompt ? " on" : ""}`}
                      />
                    </button>
                    {/* Divider */}
                    <div
                      style={{
                        height: 1,
                        background: "#f1f5f9",
                        margin: "4px 0",
                      }}
                    />

                    {/* Language selector */}
                    <div
                      className="clc-dropdown-item"
                      style={{ cursor: "default" }}
                    >
                      <span className="clc-dropdown-label">
                        <Languages size={13} /> Language
                      </span>
                      <select
                        value={language}
                        onChange={(e) => setLanguage(e.target.value)}
                        onClick={(e) => e.stopPropagation()}
                        style={{
                          fontSize: "0.7rem",
                          border: "1px solid #e2e8f0",
                          borderRadius: 6,
                          padding: "2px 4px",
                          background: "white",
                          color: "#374151",
                          cursor: "pointer",
                          outline: "none",
                        }}
                      >
                        {SUPPORTED_LANGUAGES.map((lang) => (
                          <option key={lang.code} value={lang.code}>
                            {lang.label}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                )}
              </div>

              {sending ? (
                <button
                  type="button"
                  className="clc-send-btn"
                  onClick={cancelStream}
                  style={{ background: "#fee2e2", color: "#dc2626" }}
                >
                  <X size={15} />
                </button>
              ) : (
                <button
                  type="button"
                  className="clc-send-btn"
                  onClick={handleSubmitFromInput}
                  disabled={!question.trim()}
                  style={{
                    background: !question.trim() ? "#f1f5f9" : "#7c3aed",
                    color: !question.trim() ? "#94a3b8" : "white",
                  }}
                >
                  <Send size={15} />
                </button>
              )}
            </div>
          </>
        )}

        {/* ── HISTORY VIEW ── */}
        {view === "history" && (
          <div className="clc-history">
            <div className="clc-hist-scroll">
              {loadingSessions && (
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: 8,
                    padding: 24,
                    color: "#94a3b8",
                    fontSize: "0.78rem",
                  }}
                >
                  <Loader2 size={16} className="clc-spin" /> Loading sessions…
                </div>
              )}

              {!loadingSessions && sessions.length === 0 && (
                <div className="clc-empty">
                  <div
                    style={{
                      width: 40,
                      height: 40,
                      borderRadius: 12,
                      background: "#f1f5f9",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    <MessageCircle size={18} color="#94a3b8" />
                  </div>
                  <p
                    style={{
                      fontSize: "0.82rem",
                      fontWeight: 600,
                      color: "#475569",
                      margin: 0,
                    }}
                  >
                    No chat history yet
                  </p>
                  <p
                    style={{ fontSize: "0.75rem", color: "#94a3b8", margin: 0 }}
                  >
                    Start a conversation to see it here.
                  </p>
                  <button
                    type="button"
                    onClick={() => setView("chat")}
                    style={{
                      marginTop: 8,
                      padding: "7px 16px",
                      borderRadius: 9,
                      background: "#7c3aed",
                      color: "white",
                      border: "none",
                      cursor: "pointer",
                      fontSize: "0.78rem",
                      fontWeight: 600,
                      display: "flex",
                      alignItems: "center",
                      gap: 5,
                    }}
                  >
                    <Plus size={13} /> Start chatting
                  </button>
                </div>
              )}

              {!loadingSessions && sessions.length > 0 && (
                <>
                  <p
                    style={{
                      fontSize: "0.68rem",
                      fontWeight: 700,
                      color: "#94a3b8",
                      textTransform: "uppercase",
                      letterSpacing: "0.06em",
                      padding: "4px 4px 8px",
                      margin: 0,
                    }}
                  >
                    {sessions.length} session{sessions.length !== 1 ? "s" : ""}
                  </p>
                  {sessions.map((s) => {
                    const isCurrent = s.id === sessionId;
                    const isLoading = loadingSession === s.id;
                    const isDeleting = deletingId === s.id;
                    return (
                      <div
                        key={s.id}
                        role="button"
                        tabIndex={0}
                        onClick={() => loadSessionMessages(s.id)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            loadSessionMessages(s.id);
                          }
                        }}
                        className={`clc-session-item${isCurrent ? " current" : ""}`}
                      >
                        <div className="clc-session-icon">
                          {isLoading ? (
                            <Loader2
                              size={14}
                              color={isCurrent ? "white" : "#7c3aed"}
                              className="clc-spin"
                            />
                          ) : (
                            <MessageCircle
                              size={14}
                              color={isCurrent ? "white" : "#7c3aed"}
                            />
                          )}
                        </div>

                        <div
                          style={{
                            flex: 1,
                            minWidth: 0,
                            textAlign: "left",
                          }}
                        >
                          <p
                            style={{
                              fontSize: "0.78rem",
                              fontWeight: 600,
                              color: isCurrent ? "#4c1d95" : "#0f172a",
                              margin: 0,
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                              whiteSpace: "nowrap",
                              paddingRight: 28,
                            }}
                          >
                            <SessionTitle session={s} />
                          </p>

                          <p
                            style={{
                              fontSize: "0.67rem",
                              color: isCurrent ? "#6d28d9" : "#94a3b8",
                              margin: "2px 0 0",
                              display: "flex",
                              alignItems: "center",
                              gap: 4,
                            }}
                          >
                            <Clock size={9} />
                            {formatSessionTime(s.created_at)}
                          </p>
                        </div>

                        <button
                          type="button"
                          className="clc-session-del"
                          onClick={(e) => {
                            e.stopPropagation();
                            deleteSession(s.id, e);
                          }}
                          title="Delete session"
                          disabled={isDeleting}
                          aria-label="Delete session"
                        >
                          {isDeleting ? (
                            <Loader2 size={11} className="clc-spin" />
                          ) : (
                            <Trash2 size={11} />
                          )}
                        </button>
                      </div>
                    );
                  })}
                </>
              )}
            </div>

            {/* History footer */}
            <div
              style={{
                padding: "8px 10px",
                borderTop: "1px solid #e2e8f0",
                background: "#fafafa",
                flexShrink: 0,
              }}
            >
              <button
                type="button"
                onClick={() => setView("chat")}
                style={{
                  width: "100%",
                  padding: "8px",
                  borderRadius: 9,
                  border: "1px solid #e2e8f0",
                  background: "white",
                  cursor: "pointer",
                  fontSize: "0.78rem",
                  fontWeight: 600,
                  color: "#64748b",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 6,
                  transition: "background 0.12s",
                }}
              >
                <ChevronLeft size={14} /> Back to chat
              </button>
            </div>
          </div>
        )}
      </div>
    </>
  );
}

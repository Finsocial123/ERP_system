"use client";

import { useEffect, useRef, useState } from "react";
import { Bot, Loader2, Plus, RefreshCw, Send, X } from "lucide-react";
import { createChatSession, getChatMessages, streamLessonChatMessage } from "@/lib/chatApi";
import type { ChatMessage, LMSLesson } from "@/types";

type LocalMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
};

type Props = {
  lesson: LMSLesson;
  courseTitle?: string;
  /** When true the component renders fully expanded (no toggle button) */
  embedded?: boolean;
};

function storageKey(lessonId: number) {
  return `erp_lms_lesson_chat_session_${lessonId}`;
}

function normalizeMessages(rows: ChatMessage[]): LocalMessage[] {
  return rows
    .filter((row) => row.role === "user" || row.role === "assistant")
    .map((row): LocalMessage => ({ id: String(row.id), role: row.role === "assistant" ? "assistant" : "user", content: row.content || "" }))
    .filter((row) => row.content.trim().length > 0);
}

export default function CourseLessonChat({ lesson, courseTitle, embedded = false }: Props) {
  const [open, setOpen] = useState(embedded);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<LocalMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, sending, open]);

  useEffect(() => {
    if (!open || typeof window === "undefined") return;
    const savedSessionId = localStorage.getItem(storageKey(lesson.id));
    if (!savedSessionId || savedSessionId === sessionId) return;
    setLoadingHistory(true);
    setError("");
    setSessionId(savedSessionId);
    getChatMessages(savedSessionId)
      .then((rows) => setMessages(normalizeMessages(rows)))
      .catch(() => { localStorage.removeItem(storageKey(lesson.id)); setSessionId(null); setMessages([]); })
      .finally(() => setLoadingHistory(false));
  }, [lesson.id, open, sessionId]);

  // Reset when lesson changes
  useEffect(() => {
    setMessages([]);
    setSessionId(null);
    setQuestion("");
    setError("");
  }, [lesson.id]);

  const resetChat = () => {
    if (typeof window !== "undefined") localStorage.removeItem(storageKey(lesson.id));
    setSessionId(null); setMessages([]); setQuestion(""); setError("");
  };

  const ensureSession = async () => {
    if (sessionId) return sessionId;
    const session = await createChatSession();
    setSessionId(session.id);
    if (typeof window !== "undefined") localStorage.setItem(storageKey(lesson.id), session.id);
    return session.id;
  };

  const submitQuestion = async () => {
    const clean = question.trim();
    if (!clean || sending) return;
    setSending(true); setError(""); setQuestion("");
    const userMsg: LocalMessage = { id: `user-${Date.now()}`, role: "user", content: clean };
    const assistantId = `assistant-${Date.now()}`;
    const assistantMsg: LocalMessage = { id: assistantId, role: "assistant", content: "" };
    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    try {
      const sid = await ensureSession();
      let answer = "";
      await streamLessonChatMessage({
        sessionId: sid, content: clean, lessonId: lesson.id,
        language: lesson.language || "en", webSearch: false, enhancePrompt: false,
        callbacks: {
          onToken: (token) => {
            answer += token;
            setMessages((prev) => prev.map((m) => m.id === assistantId ? { ...m, content: answer } : m));
          },
        },
      });
      if (!answer.trim()) {
        setMessages((prev) => prev.map((m) => m.id === assistantId ? { ...m, content: "I could not generate a response. Please try again." } : m));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send question");
      setMessages((prev) => prev.filter((m) => m.id !== assistantId));
    } finally {
      setSending(false);
    }
  };

  // ── Standalone / legacy mode (toggle button) ──
  if (!embedded) {
    return (
      <div style={{ borderRadius: 14, border: "1px solid #e2e8f0", background: "#f8fafc", marginTop: 12 }}>
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          style={{ display: "flex", width: "100%", alignItems: "center", justifyContent: "space-between", gap: 10, padding: "10px 14px", background: "none", border: "none", cursor: "pointer" }}
        >
          <span style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "0.8125rem", fontWeight: 600, color: "#0f172a" }}>
            <span style={{ borderRadius: 8, background: "#0f172a", padding: "5px 6px", display: "flex", alignItems: "center" }}>
              <Bot size={14} color="white" />
            </span>
            Ask AI about this lesson
          </span>
          <span style={{ color: "#94a3b8" }}>{open ? <X size={16} /> : <span style={{ fontSize: "0.75rem" }}>Open</span>}</span>
        </button>
        {open && <ChatBody messages={messages} loadingHistory={loadingHistory} sending={sending} error={error} question={question} setQuestion={setQuestion} submitQuestion={submitQuestion} resetChat={resetChat} lesson={lesson} courseTitle={courseTitle} bottomRef={bottomRef} />}
      </div>
    );
  }

  // ── Embedded mode (always open, no toggle) ──
  return (
    <ChatBody
      messages={messages}
      loadingHistory={loadingHistory}
      sending={sending}
      error={error}
      question={question}
      setQuestion={setQuestion}
      submitQuestion={submitQuestion}
      resetChat={resetChat}
      lesson={lesson}
      courseTitle={courseTitle}
      bottomRef={bottomRef}
      fullHeight
    />
  );
}

type ChatBodyProps = {
  messages: LocalMessage[];
  loadingHistory: boolean;
  sending: boolean;
  error: string;
  question: string;
  setQuestion: (v: string) => void;
  submitQuestion: () => void;
  resetChat: () => void;
  lesson: LMSLesson;
  courseTitle?: string;
  bottomRef: React.RefObject<HTMLDivElement | null>;
  fullHeight?: boolean;
};

function ChatBody({ messages, loadingHistory, sending, error, question, setQuestion, submitQuestion, resetChat, lesson, courseTitle, bottomRef, fullHeight }: ChatBodyProps) {
  return (
    <div style={{ display: "flex", flexDirection: "column", flex: fullHeight ? 1 : undefined, minHeight: fullHeight ? 0 : undefined, padding: fullHeight ? 0 : "0 12px 12px", borderTop: fullHeight ? undefined : "1px solid #e2e8f0" }}>
      {/* Sub-header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 0 8px", flexShrink: 0 }}>
        <div>
          <p style={{ fontSize: "0.75rem", fontWeight: 700, color: "#0f172a", margin: 0 }}>Lesson Chatbot</p>
          <p style={{ fontSize: "0.65rem", color: "#94a3b8", margin: "1px 0 0" }}>
            {courseTitle ? `${courseTitle} · ` : ""}{lesson.title}
          </p>
        </div>
        <button
          type="button"
          onClick={resetChat}
          style={{ display: "flex", alignItems: "center", gap: 4, padding: "4px 9px", borderRadius: 7, border: "1px solid #e2e8f0", background: "white", fontSize: "0.7rem", fontWeight: 600, color: "#64748b", cursor: "pointer", flexShrink: 0 }}
        >
          <Plus size={11} /> New chat
        </button>
      </div>

      {error && (
        <div style={{ marginBottom: 8, padding: "7px 10px", background: "#fee2e2", borderRadius: 8, fontSize: "0.75rem", color: "#991b1b" }}>{error}</div>
      )}

      {/* Messages */}
      <div style={{
        flex: 1, minHeight: 0, overflowY: "auto", padding: "8px",
        background: "white", borderRadius: 10, border: "1px solid #e2e8f0",
        marginBottom: 8, display: "flex", flexDirection: "column", gap: 6,
        scrollbarWidth: "thin", scrollbarColor: "#cbd5e1 transparent",
      }}>
        {loadingHistory && (
          <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "0.75rem", color: "#94a3b8" }}>
            <Loader2 size={13} className="animate-spin" /> Loading…
          </div>
        )}
        {!loadingHistory && messages.length === 0 && (
          <div style={{ padding: "10px 12px", background: "#eff6ff", borderRadius: 8, fontSize: "0.75rem", color: "#1d4ed8", lineHeight: 1.5 }}>
            Try: <em>"Explain this topic simply"</em> or <em>"What is the key concept?"</em>
          </div>
        )}
        {messages.map((msg) => (
          <div key={msg.id} style={{ display: "flex", justifyContent: msg.role === "user" ? "flex-end" : "flex-start" }}>
            <div style={{
              maxWidth: "88%", padding: "7px 10px", borderRadius: msg.role === "user" ? "12px 12px 3px 12px" : "12px 12px 12px 3px",
              background: msg.role === "user" ? "#0f172a" : "#f1f5f9",
              color: msg.role === "user" ? "white" : "#1e293b",
              fontSize: "0.78rem", lineHeight: 1.55, whiteSpace: "pre-wrap",
            }}>
              {msg.content || (msg.role === "assistant" && sending ? (
                <span style={{ display: "flex", alignItems: "center", gap: 5, color: "#94a3b8" }}>
                  <Loader2 size={12} className="animate-spin" /> Thinking…
                </span>
              ) : null)}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask your doubt…"
          rows={2}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submitQuestion(); } }}
          style={{
            flex: 1, resize: "none", border: "1px solid #e2e8f0", borderRadius: 10,
            padding: "8px 10px", fontSize: "0.78rem", outline: "none", fontFamily: "inherit",
            transition: "border-color 0.13s", lineHeight: 1.5,
          }}
          onFocus={(e) => (e.target.style.borderColor = "#a78bfa")}
          onBlur={(e) => (e.target.style.borderColor = "#e2e8f0")}
        />
        <button
          type="button"
          onClick={submitQuestion}
          disabled={sending || !question.trim()}
          style={{
            padding: "0 12px", borderRadius: 10, border: "none",
            background: sending || !question.trim() ? "#e2e8f0" : "#7c3aed",
            color: sending || !question.trim() ? "#94a3b8" : "white",
            cursor: sending || !question.trim() ? "not-allowed" : "pointer",
            display: "flex", alignItems: "center", justifyContent: "center",
            transition: "background 0.13s",
          }}
        >
          {sending ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
        </button>
      </div>
    </div>
  );
}

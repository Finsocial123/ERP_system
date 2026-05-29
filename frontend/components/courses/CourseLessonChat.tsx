"use client";

import { useEffect, useRef, useState } from "react";
import { Bot, Loader2, MessageCircle, RefreshCw, Send, X } from "lucide-react";

import { Button, Textarea } from "@/components/ui";
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
};

function storageKey(lessonId: number) {
  return `erp_lms_lesson_chat_session_${lessonId}`;
}

function normalizeMessages(rows: ChatMessage[]): LocalMessage[] {
  return rows
    .filter((row) => row.role === "user" || row.role === "assistant")
    .map((row): LocalMessage => ({
      id: String(row.id),
      role: row.role === "assistant" ? "assistant" : "user",
      content: row.content || "",
    }))
    .filter((row) => row.content.trim().length > 0);
}

export default function CourseLessonChat({ lesson, courseTitle }: Props) {
  const [open, setOpen] = useState(false);
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
      .catch(() => {
        localStorage.removeItem(storageKey(lesson.id));
        setSessionId(null);
        setMessages([]);
      })
      .finally(() => setLoadingHistory(false));
  }, [lesson.id, open, sessionId]);

  const resetChat = () => {
    if (typeof window !== "undefined") localStorage.removeItem(storageKey(lesson.id));
    setSessionId(null);
    setMessages([]);
    setQuestion("");
    setError("");
  };

  const ensureSession = async () => {
    if (sessionId) return sessionId;
    const session = await createChatSession();
    setSessionId(session.id);
    if (typeof window !== "undefined") localStorage.setItem(storageKey(lesson.id), session.id);
    return session.id;
  };

  const submitQuestion = async () => {
    const cleanQuestion = question.trim();
    if (!cleanQuestion || sending) return;

    setSending(true);
    setError("");
    setQuestion("");

    const userMessage: LocalMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: cleanQuestion,
    };
    const assistantId = `assistant-${Date.now()}`;
    const assistantMessage: LocalMessage = {
      id: assistantId,
      role: "assistant",
      content: "",
    };

    setMessages((prev) => [...prev, userMessage, assistantMessage]);

    try {
      const activeSessionId = await ensureSession();
      let answer = "";

      await streamLessonChatMessage({
        sessionId: activeSessionId,
        content: cleanQuestion,
        lessonId: lesson.id,
        language: lesson.language || "en",
        webSearch: false,
        enhancePrompt: false,
        callbacks: {
          onToken: (token) => {
            answer += token;
            setMessages((prev) => prev.map((msg) => (msg.id === assistantId ? { ...msg, content: answer } : msg)));
          },
        },
      });

      if (!answer.trim()) {
        setMessages((prev) => prev.map((msg) => (msg.id === assistantId ? { ...msg, content: "I could not generate a response. Please try again." } : msg)));
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to send question";
      setError(message);
      setMessages((prev) => prev.filter((msg) => msg.id !== assistantId));
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left"
      >
        <span className="flex items-center gap-2 text-sm font-semibold text-slate-900">
          <span className="rounded-xl bg-slate-900 p-2 text-white"><Bot size={16} /></span>
          Ask AI about this lesson
        </span>
        <span className="text-slate-500">{open ? <X size={18} /> : <MessageCircle size={18} />}</span>
      </button>

      {open && (
        <div className="border-t border-slate-200 p-4">
          <div className="mb-3 flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-slate-900">Lesson chatbot</p>
              <p className="text-xs text-slate-500">
                Ask doubts from {courseTitle ? `${courseTitle} · ` : ""}{lesson.title}. Your question is sent with this lesson ID.
              </p>
            </div>
            <button
              type="button"
              onClick={resetChat}
              className="inline-flex items-center gap-1 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100"
            >
              <RefreshCw size={14} /> New chat
            </button>
          </div>

          {error && <div className="mb-3 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}

          <div className="mb-3 max-h-80 space-y-3 overflow-y-auto rounded-2xl border border-slate-200 bg-white p-3">
            {loadingHistory && (
              <div className="flex items-center gap-2 text-sm text-slate-500"><Loader2 size={16} className="animate-spin" /> Loading chat...</div>
            )}

            {!loadingHistory && messages.length === 0 && (
              <div className="rounded-xl bg-blue-50 px-3 py-3 text-sm text-blue-700">
                Example: “Explain this topic in simple words” or “What is the main concept in this lesson?”
              </div>
            )}

            {messages.map((msg) => (
              <div key={msg.id} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-3 py-2 text-sm ${msg.role === "user" ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-800"}`}>
                  {msg.content || (msg.role === "assistant" && sending ? <span className="inline-flex items-center gap-2 text-slate-500"><Loader2 size={14} className="animate-spin" /> Thinking...</span> : null)}
                </div>
              </div>
            ))}
            <div ref={bottomRef} />
          </div>

          <div className="grid gap-2 md:grid-cols-[1fr_auto]">
            <Textarea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Ask your doubt about this lesson..."
              className="min-h-20 bg-white"
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  submitQuestion();
                }
              }}
            />
            <Button type="button" onClick={submitQuestion} disabled={sending || !question.trim()} className="inline-flex h-fit items-center justify-center gap-2">
              {sending ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
              Send
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

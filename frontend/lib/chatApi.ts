import { apiFetch, authFetch } from "@/lib/api";
import type { ChatMessage, ChatSession } from "@/types";

export async function createChatSession(): Promise<ChatSession> {
  return apiFetch<ChatSession>("/sessions", { method: "POST" });
}

export async function getChatSessions(): Promise<ChatSession[]> {
  return apiFetch<ChatSession[]>("/sessions");
}

export async function getChatMessages(
  sessionId: string,
): Promise<ChatMessage[]> {
  return apiFetch<ChatMessage[]>(`/sessions/${sessionId}/messages`);
}

type StreamCallbacks = {
  onToken: (token: string) => void;
  onEnhancedPrompt?: (content: string) => void;
  onSuggestedQuestions?: (questions: string[]) => void;
  onStatus?: (status: string) => void;
};

function parseSseDataLine(line: string): unknown | null {
  if (!line.startsWith("data:")) return null;

  const raw = line.slice(5).trim();
  if (!raw) return null;

  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export async function streamLessonChatMessage(params: {
  sessionId: string;
  content: string;
  lessonId: number;
  language?: string | null;
  webSearch?: boolean;
  enhancePrompt?: boolean;
  signal?: AbortSignal;
  callbacks: StreamCallbacks;
}): Promise<void> {
  const res = await authFetch(`/sessions/${params.sessionId}/messages`, {
    method: "POST",
    signal: params.signal,
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      content: params.content,
      lesson_id: params.lessonId,
      web_search: Boolean(params.webSearch),
      enhance_prompt: Boolean(params.enhancePrompt),
      language: params.language || "en",
    }),
  });

  if (!res.ok) {
    const contentType = res.headers.get("content-type") || "";
    const data: unknown = contentType.includes("application/json")
      ? await res.json()
      : await res.text();

    const detail =
      typeof data === "object" && data && "detail" in data
        ? (data as { detail?: unknown }).detail
        : null;

    const message =
      typeof detail === "string" ? detail : "Failed to send message";
    throw new Error(message);
  }

  if (!res.body) {
    throw new Error("Chat stream is not available");
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      const parsed = parseSseDataLine(line);
      if (!parsed || typeof parsed !== "object") continue;

      const payload = parsed as {
        token?: string;
        error?: string;
        status?: string;
        enhanced_prompt?: string;
        suggested_questions?: unknown;
      };

      if (payload.error) throw new Error(payload.error);
      if (payload.enhanced_prompt)
        params.callbacks.onEnhancedPrompt?.(payload.enhanced_prompt);
      if (Array.isArray(payload.suggested_questions)) {
        const questions = payload.suggested_questions
          .filter((item): item is string => typeof item === "string")
          .map((item) => item.trim())
          .filter(Boolean);
        if (questions.length) params.callbacks.onSuggestedQuestions?.(questions);
      }
      if (payload.status) params.callbacks.onStatus?.(payload.status);
      if (payload.token) params.callbacks.onToken(payload.token);
    }
  }

  const tail = parseSseDataLine(buffer);
  if (tail && typeof tail === "object") {
    const payload = tail as {
      token?: string;
      error?: string;
      status?: string;
      enhanced_prompt?: string;
      suggested_questions?: unknown;
    };

    if (payload.error) throw new Error(payload.error);
    if (payload.enhanced_prompt)
      params.callbacks.onEnhancedPrompt?.(payload.enhanced_prompt);
    if (Array.isArray(payload.suggested_questions)) {
      const questions = payload.suggested_questions
        .filter((item): item is string => typeof item === "string")
        .map((item) => item.trim())
        .filter(Boolean);
      if (questions.length) params.callbacks.onSuggestedQuestions?.(questions);
    }
    if (payload.status) params.callbacks.onStatus?.(payload.status);
    if (payload.token) params.callbacks.onToken(payload.token);
  }
}

export type ChatShareResponse = {
  ok: boolean;
  channel: "email" | "telegram" | string;
  message: string;
};

export async function sendChatAnswerEmail(params: {
  content: string;
  toEmail?: string;
  subject?: string;
  lessonTitle?: string;
  courseTitle?: string;
}): Promise<ChatShareResponse> {
  return apiFetch<ChatShareResponse>("/sessions/share/email", {
    method: "POST",
    body: JSON.stringify({
      content: params.content,
      to_email: params.toEmail || null,
      subject: params.subject || null,
      lesson_title: params.lessonTitle || null,
      course_title: params.courseTitle || null,
    }),
  });
}

export async function sendChatAnswerTelegram(params: {
  content: string;
  chatId?: string;
  lessonTitle?: string;
  courseTitle?: string;
}): Promise<ChatShareResponse> {
  return apiFetch<ChatShareResponse>("/sessions/share/telegram", {
    method: "POST",
    body: JSON.stringify({
      content: params.content,
      chat_id: params.chatId || null,
      lesson_title: params.lessonTitle || null,
      course_title: params.courseTitle || null,
    }),
  });
}

import { API_BASE, apiFetch, getToken } from "@/lib/api";
import type { ChatMessage, ChatSession } from "@/types";

export async function createChatSession(): Promise<ChatSession> {
  return apiFetch<ChatSession>("/sessions", { method: "POST" });
}

export async function getChatSessions(): Promise<ChatSession[]> {
  return apiFetch<ChatSession[]>("/sessions");
}

export async function getChatMessages(sessionId: string): Promise<ChatMessage[]> {
  return apiFetch<ChatMessage[]>(`/sessions/${sessionId}/messages`);
}

type StreamCallbacks = {
  onToken: (token: string) => void;
  onEnhancedPrompt?: (content: string) => void;
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
  callbacks: StreamCallbacks;
}): Promise<void> {
  const token = getToken();

  const res = await fetch(`${API_BASE}/sessions/${params.sessionId}/messages`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
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

    const message = typeof detail === "string" ? detail : "Failed to send message";
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
      };

      if (payload.error) throw new Error(payload.error);
      if (payload.enhanced_prompt) params.callbacks.onEnhancedPrompt?.(payload.enhanced_prompt);
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
    };

    if (payload.error) throw new Error(payload.error);
    if (payload.enhanced_prompt) params.callbacks.onEnhancedPrompt?.(payload.enhanced_prompt);
    if (payload.status) params.callbacks.onStatus?.(payload.status);
    if (payload.token) params.callbacks.onToken(payload.token);
  }
}
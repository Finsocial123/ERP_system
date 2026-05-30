import { API_BASE, apiFetch, getToken } from "@/lib/api";

export type QuizRequest = {
  num_questions?: number;
  difficulty?: "easy" | "medium" | "hard";
};

export type QuizQuestion = {
  question: string;
  options: string[];
  correct_answer: string;
  explanation?: string;
};

export type QuizResponse = {
  questions: QuizQuestion[];
  title?: string;
  description?: string;
};

export async function generateLessonQuiz(
  courseId: number,
  lessonId: number,
  request: QuizRequest = {}
): Promise<QuizResponse> {
  const token = getToken();

  // Endpoint: /assignments/course/{course_id}/lessons/{lesson_id}/quiz
  const endpoint = `/assignments/api/course/${courseId}/lessons/${lessonId}/quiz`;

  const res = await fetch(`${API_BASE}${endpoint}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({
      num_questions: request.num_questions || 5,
      difficulty: request.difficulty || "medium",
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
      typeof detail === "string" ? detail : "Failed to generate quiz";
    throw new Error(message);
  }

  return res.json();
}

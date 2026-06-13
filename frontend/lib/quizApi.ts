import { apiFetch } from "@/lib/api";

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
  // Endpoint: /assignments/course/{course_id}/lessons/{lesson_id}/quiz
  const endpoint = `/assignments/api/course/${courseId}/lessons/${lessonId}/quiz`;

  return apiFetch<QuizResponse>(endpoint, {
    method: "POST",
    body: JSON.stringify({
      num_questions: request.num_questions || 5,
      difficulty: request.difficulty || "medium",
    }),
  });
}

import { apiFetch } from "@/lib/api";

export type SummaryRequest = {
  source: "transcript" | "notes" | "visual";
};

export type SummaryResponse = {
  summary: string;
  title?: string;
  key_points?: string[];
  source: string;
};

export async function generateLessonSummary(
  courseId: number,
  lessonId: number,
  source: "transcript" | "notes" | "visual"
): Promise<SummaryResponse> {
  const endpoint = `/lessons/${lessonId}/course/${courseId}/${source}/summary`;

  return apiFetch<SummaryResponse>(endpoint, { method: "POST" });
}

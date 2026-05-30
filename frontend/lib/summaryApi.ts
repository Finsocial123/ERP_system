import { API_BASE, getToken } from "@/lib/api";

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
  const token = getToken();

  const endpoint = `/lessons/${lessonId}/course/${courseId}/${source}/summary`;

  const res = await fetch(`${API_BASE}${endpoint}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
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
      typeof detail === "string" ? detail : "Failed to generate summary";
    throw new Error(message);
  }

  return res.json();
}

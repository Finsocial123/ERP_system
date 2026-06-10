"use client";

import AppShell from "@/components/AppShell";
import { useState, useEffect } from "react";
import { BookOpen, Loader2, AlertCircle } from "lucide-react";
import { apiFetch } from "@/lib/api";
import type { LMSCourse, LMSLesson } from "@/types";
import LessonQuizGenerator from "@/components/courses/LessonQuizGenerator";
import { Button } from "@/components/ui";

export default function QuizGeneratorPage() {
  const [courses, setCourses] = useState<LMSCourse[]>([]);
  const [selectedCourse, setSelectedCourse] = useState<LMSCourse | null>(null);
  const [lessons, setLessons] = useState<LMSLesson[]>([]);
  const [selectedLesson, setSelectedLesson] = useState<LMSLesson | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Fetch student's enrolled courses
  useEffect(() => {
    const fetchCourses = async () => {
      try {
        setLoading(true);
        const data = await apiFetch<LMSCourse[]>("/courses/enrolled");
        setCourses(data);
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to load courses";
        setError(message);
      } finally {
        setLoading(false);
      }
    };

    fetchCourses();
  }, []);

  // Fetch lessons when course is selected
  useEffect(() => {
    if (!selectedCourse) {
      setLessons([]);
      return;
    }

    const fetchLessons = async () => {
      try {
        setLoading(true);
        const data = await apiFetch<LMSLesson[]>(
          `/lessons/course/${selectedCourse.id}`
        );
        setLessons(data);
        setSelectedLesson(null);
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to load lessons";
        setError(message);
      } finally {
        setLoading(false);
      }
    };

    fetchLessons();
  }, [selectedCourse]);

  return (
    <AppShell>
      <div className="max-w-5xl mx-auto p-6">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3 mb-2">
            <BookOpen className="text-blue-600" size={32} />
            Quiz Generator
          </h1>
          <p className="text-gray-600">
            Generate AI-powered quizzes for your course lessons to test your knowledge
          </p>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg flex items-start gap-3">
            <AlertCircle className="text-red-600 shrink-0 mt-0.5" />
            <div>
              <h3 className="font-semibold text-red-900">Error</h3>
              <p className="text-red-700">{error}</p>
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Step 1: Select Course */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-lg shadow p-6 sticky top-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                Step 1: Select Course
              </h2>

              {loading && courses.length === 0 ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="animate-spin text-blue-600" size={24} />
                </div>
              ) : courses.length === 0 ? (
                <p className="text-gray-600 text-sm">
                  No enrolled courses found. Start by enrolling in a course.
                </p>
              ) : (
                <div className="space-y-2">
                  {courses.map((course) => (
                    <button
                      key={course.id}
                      onClick={() => setSelectedCourse(course)}
                      className={`w-full text-left p-3 rounded-lg transition-colors ${
                        selectedCourse?.id === course.id
                          ? "bg-blue-600 text-white"
                          : "bg-gray-50 text-gray-900 hover:bg-gray-100"
                      }`}
                    >
                      <div className="font-medium">{course.title}</div>
                      <div
                        className={`text-xs ${
                          selectedCourse?.id === course.id
                            ? "text-blue-100"
                            : "text-gray-500"
                        }`}
                      >
                        {course.lessons_count} lessons
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Step 2: Select Lesson and Step 3: Generate Quiz */}
          <div className="lg:col-span-2 space-y-6">
            {/* Step 2: Select Lesson */}
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                Step 2: Select Lesson
              </h2>

              {!selectedCourse ? (
                <div className="text-center py-8">
                  <p className="text-gray-600">
                    Please select a course first
                  </p>
                </div>
              ) : loading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="animate-spin text-blue-600" size={24} />
                </div>
              ) : lessons.length === 0 ? (
                <p className="text-gray-600">No lessons available in this course</p>
              ) : (
                <div className="grid gap-3">
                  {lessons.map((lesson) => (
                    <button
                      key={lesson.id}
                      onClick={() => setSelectedLesson(lesson)}
                      className={`p-4 rounded-lg border-2 transition-colors text-left ${
                        selectedLesson?.id === lesson.id
                          ? "border-blue-600 bg-blue-50"
                          : "border-gray-200 bg-white hover:border-blue-300"
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <div>
                          <h3 className="font-semibold text-gray-900">
                            Lesson {lesson.order}: {lesson.title}
                          </h3>
                          {lesson.description && (
                            <p className="text-sm text-gray-600 mt-1">
                              {lesson.description.substring(0, 100)}
                              {lesson.description.length > 100 ? "..." : ""}
                            </p>
                          )}
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Step 3: Generate Quiz */}
            {selectedLesson && (
              <div className="bg-white rounded-lg shadow p-6">
                <h2 className="text-lg font-semibold text-gray-900 mb-4">
                  Step 3: Generate Quiz
                </h2>
                <p className="text-gray-600 mb-4">
                  Selected: <span className="font-semibold">{selectedLesson.title}</span>
                </p>
                <LessonQuizGenerator lesson={selectedLesson} courseTitle={selectedCourse?.title} />
              </div>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  );
}

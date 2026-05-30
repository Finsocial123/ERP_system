"use client";

import { useState } from "react";
import { BookOpen, Loader2, AlertCircle, CheckCircle, XCircle, RefreshCw } from "lucide-react";
import { generateLessonQuiz, QuizResponse, QuizQuestion } from "@/lib/quizApi";
import type { LMSLesson } from "@/types";

type Props = {
  lesson: LMSLesson;
  courseTitle?: string;
  /** When true the component renders without a trigger button */
  embedded?: boolean;
};

type QuizState = "idle" | "generating" | "taking" | "completed" | "error";
type AnswerMap = Record<number, string>;

export default function LessonQuizGenerator({ lesson, courseTitle, embedded = false }: Props) {
  const [open, setOpen] = useState(embedded);
  const [state, setState] = useState<QuizState>("idle");
  const [quiz, setQuiz] = useState<QuizResponse | null>(null);
  const [answers, setAnswers] = useState<AnswerMap>({});
  const [error, setError] = useState("");
  const [numQuestions, setNumQuestions] = useState(5);
  const [difficulty, setDifficulty] = useState<"easy" | "medium" | "hard">("medium");

  // Reset when lesson changes
  const handleReset = () => { setState("idle"); setQuiz(null); setAnswers({}); setError(""); };
  const handleClose = () => { handleReset(); if (!embedded) setOpen(false); };

  // Also reset on lesson change
  const lessonIdRef = { current: lesson.id };
  if (lessonIdRef.current !== lesson.id) { handleReset(); }

  const handleGenerateQuiz = async () => {
    setState("generating"); setError("");
    try {
      const data = await generateLessonQuiz(lesson.course_id, lesson.id, { num_questions: numQuestions, difficulty });
      setQuiz(data); setState("taking"); setAnswers({});
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate quiz");
      setState("error");
    }
  };

  const handleSubmitQuiz = () => { if (quiz) setState("completed"); };

  if (!embedded && !open) {
    return (
      <button
        onClick={() => setOpen(true)}
        style={{ display: "flex", alignItems: "center", gap: 6, padding: "7px 14px", borderRadius: 9, background: "#eff6ff", color: "#2563eb", border: "none", cursor: "pointer", fontSize: "0.8rem", fontWeight: 600, transition: "background 0.13s" }}
        onMouseEnter={(e) => ((e.target as HTMLElement).style.background = "#dbeafe")}
        onMouseLeave={(e) => ((e.target as HTMLElement).style.background = "#eff6ff")}
      >
        <BookOpen size={15} /> Generate Quiz
      </button>
    );
  }

  if (!embedded && open) {
    return (
      <div style={{ position: "fixed", inset: 0, zIndex: 50, background: "rgba(15,23,42,0.55)", display: "flex", alignItems: "center", justifyContent: "center", padding: 16, overflowY: "auto" }}>
        <div style={{ background: "white", borderRadius: 16, boxShadow: "0 24px 64px rgba(0,0,0,0.18)", width: "100%", maxWidth: 560, maxHeight: "90vh", overflowY: "auto" }}>
          <div style={{ background: "linear-gradient(135deg,#2563eb,#1d4ed8)", padding: "20px 24px", borderRadius: "16px 16px 0 0", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <BookOpen size={20} color="white" />
              <div>
                <h2 style={{ fontSize: "1rem", fontWeight: 700, color: "white", margin: 0 }}>Quiz Generator</h2>
                <p style={{ fontSize: "0.72rem", color: "#bfdbfe", margin: 0 }}>{lesson.title}</p>
              </div>
            </div>
            <button onClick={handleClose} style={{ background: "rgba(255,255,255,0.15)", border: "none", borderRadius: 8, padding: "4px 8px", color: "white", cursor: "pointer", fontSize: "0.8rem" }}>✕</button>
          </div>
          <div style={{ padding: 24 }}>
            <QuizContent state={state} quiz={quiz} answers={answers} error={error} numQuestions={numQuestions} difficulty={difficulty} setNumQuestions={setNumQuestions} setDifficulty={setDifficulty} setAnswers={(idx, val) => setAnswers((p) => ({ ...p, [idx]: val }))} onGenerate={handleGenerateQuiz} onSubmit={handleSubmitQuiz} onReset={handleReset} onClose={handleClose} />
          </div>
        </div>
      </div>
    );
  }

  // Embedded — just the content inline
  return (
    <div style={{ flex: 1, minHeight: 0, overflowY: "auto", scrollbarWidth: "thin", scrollbarColor: "#cbd5e1 transparent" }}>
      <QuizContent state={state} quiz={quiz} answers={answers} error={error} numQuestions={numQuestions} difficulty={difficulty} setNumQuestions={setNumQuestions} setDifficulty={setDifficulty} setAnswers={(idx, val) => setAnswers((p) => ({ ...p, [idx]: val }))} onGenerate={handleGenerateQuiz} onSubmit={handleSubmitQuiz} onReset={handleReset} onClose={handleClose} embedded />
    </div>
  );
}

type QuizContentProps = {
  state: QuizState; quiz: QuizResponse | null; answers: AnswerMap; error: string;
  numQuestions: number; difficulty: "easy" | "medium" | "hard";
  setNumQuestions: (n: number) => void;
  setDifficulty: (d: "easy" | "medium" | "hard") => void;
  setAnswers: (idx: number, val: string) => void;
  onGenerate: () => void; onSubmit: () => void; onReset: () => void; onClose: () => void;
  embedded?: boolean;
};

function QuizContent({ state, quiz, answers, error, numQuestions, difficulty, setNumQuestions, setDifficulty, setAnswers, onGenerate, onSubmit, onReset, onClose, embedded }: QuizContentProps) {
  const btnBase: React.CSSProperties = { border: "none", borderRadius: 9, padding: "8px 16px", fontSize: "0.8rem", fontWeight: 600, cursor: "pointer", transition: "background 0.13s" };

  if (state === "idle") return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div>
        <p style={{ fontSize: "0.72rem", fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>Questions</p>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {[3, 5, 10, 15].map((n) => (
            <button key={n} onClick={() => setNumQuestions(n)}
              style={{ ...btnBase, background: numQuestions === n ? "#2563eb" : "#f1f5f9", color: numQuestions === n ? "white" : "#475569", padding: "6px 14px" }}>
              {n}
            </button>
          ))}
        </div>
      </div>
      <div>
        <p style={{ fontSize: "0.72rem", fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>Difficulty</p>
        <div style={{ display: "flex", gap: 6 }}>
          {(["easy", "medium", "hard"] as const).map((d) => (
            <button key={d} onClick={() => setDifficulty(d)}
              style={{ ...btnBase, background: difficulty === d ? "#2563eb" : "#f1f5f9", color: difficulty === d ? "white" : "#475569", padding: "6px 14px", textTransform: "capitalize" }}>
              {d}
            </button>
          ))}
        </div>
      </div>
      <button onClick={onGenerate} style={{ ...btnBase, background: "#2563eb", color: "white", width: "100%", padding: "10px" }}>
        Generate Quiz
      </button>
    </div>
  );

  if (state === "generating") return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", padding: "32px 0", gap: 10 }}>
      <Loader2 size={28} color="#2563eb" className="animate-spin" />
      <p style={{ fontSize: "0.85rem", color: "#64748b", margin: 0 }}>Generating quiz…</p>
    </div>
  );

  if (state === "taking" && quiz) return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {quiz.questions.map((q: QuizQuestion, qi: number) => (
        <div key={qi} style={{ padding: "12px 14px", border: "1px solid #e2e8f0", borderRadius: 12, background: "#f8fafc" }}>
          <p style={{ fontSize: "0.8rem", fontWeight: 600, color: "#0f172a", margin: "0 0 10px" }}>
            <span style={{ color: "#2563eb" }}>Q{qi + 1}: </span>{q.question}
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {Object.entries(q.options).map(([key, opt]) => (
              <label key={key} style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 10px", borderRadius: 8, cursor: "pointer", background: answers[qi] === key ? "#dbeafe" : "transparent", transition: "background 0.1s", fontSize: "0.78rem", color: "#334155" }}>
                <input type="radio" name={`q-${qi}`} value={key} checked={answers[qi] === key} onChange={(e) => setAnswers(qi, e.target.value)} style={{ accentColor: "#2563eb" }} />
                <span>{opt as string}</span>
              </label>
            ))}
          </div>
        </div>
      ))}
      <button onClick={onSubmit} disabled={Object.keys(answers).length < quiz.questions.length}
        style={{ ...btnBase, background: Object.keys(answers).length < quiz.questions.length ? "#e2e8f0" : "#2563eb", color: Object.keys(answers).length < quiz.questions.length ? "#94a3b8" : "white", width: "100%", padding: 10, cursor: Object.keys(answers).length < quiz.questions.length ? "not-allowed" : "pointer" }}>
        Submit Quiz
      </button>
    </div>
  );

  if (state === "completed" && quiz) {
    const score = quiz.questions.reduce((acc: number, q: QuizQuestion, i: number) => acc + (answers[i] === q.correct_answer ? 1 : 0), 0);
    const pct = Math.round((score / quiz.questions.length) * 100);
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <div style={{ padding: "16px", background: "linear-gradient(135deg,#eff6ff,#e0f2fe)", borderRadius: 12, border: "1px solid #bfdbfe", textAlign: "center" }}>
          <div style={{ fontSize: "2rem", fontWeight: 800, color: "#2563eb" }}>{score}/{quiz.questions.length}</div>
          <div style={{ fontSize: "1.2rem", fontWeight: 700, color: "#1e40af" }}>{pct}%</div>
          <div style={{ fontSize: "0.8rem", color: "#475569", marginTop: 4 }}>
            {pct >= 80 ? "🎉 Excellent!" : pct >= 60 ? "👍 Good effort!" : "📚 Keep practicing!"}
          </div>
        </div>
        {quiz.questions.map((q: QuizQuestion, i: number) => {
          const correct = answers[i] === q.correct_answer;
          return (
            <div key={i} style={{ padding: "10px 12px", borderRadius: 10, border: `1px solid ${correct ? "#a7f3d0" : "#fecaca"}`, background: correct ? "#f0fdf4" : "#fef2f2" }}>
              <div style={{ display: "flex", gap: 8 }}>
                {correct ? <CheckCircle size={15} color="#10b981" style={{ flexShrink: 0, marginTop: 2 }} /> : <XCircle size={15} color="#ef4444" style={{ flexShrink: 0, marginTop: 2 }} />}
                <div>
                  <p style={{ fontSize: "0.78rem", fontWeight: 600, color: "#0f172a", margin: "0 0 4px" }}>Q{i + 1}: {q.question}</p>
                  <p style={{ fontSize: "0.72rem", color: "#64748b", margin: "0 0 2px" }}>Your answer: <strong>{answers[i] || "—"}</strong></p>
                  {!correct && <p style={{ fontSize: "0.72rem", color: "#10b981", fontWeight: 600, margin: 0 }}>Correct: {q.correct_answer}</p>}
                  {q.explanation && <p style={{ fontSize: "0.72rem", color: "#64748b", fontStyle: "italic", margin: "4px 0 0" }}>{q.explanation}</p>}
                </div>
              </div>
            </div>
          );
        })}
        <button onClick={onReset} style={{ ...btnBase, background: "#2563eb", color: "white", width: "100%", padding: 10 }}>
          Generate Another Quiz
        </button>
      </div>
    );
  }

  if (state === "error") return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ padding: "12px 14px", background: "#fef2f2", borderRadius: 10, border: "1px solid #fecaca", display: "flex", gap: 8 }}>
        <AlertCircle size={16} color="#ef4444" style={{ flexShrink: 0, marginTop: 1 }} />
        <p style={{ fontSize: "0.78rem", color: "#991b1b", margin: 0 }}>{error}</p>
      </div>
      <div style={{ display: "flex", gap: 8 }}>
        <button onClick={onReset} style={{ ...btnBase, flex: 1, background: "#2563eb", color: "white" }}>Try Again</button>
        <button onClick={onClose} style={{ ...btnBase, flex: 1, background: "#f1f5f9", color: "#475569" }}>Close</button>
      </div>
    </div>
  );

  return null;
}
